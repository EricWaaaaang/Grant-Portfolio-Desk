import csv, io, json, re, zipfile
import os
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from datetime import date, datetime
from pathlib import Path, PurePosixPath
from collections import defaultdict
from xlsxwriter import Workbook

MAX_UNCOMPRESSED = 150 * 1024 * 1024

def _csv(data):
    return list(csv.DictReader(io.StringIO(data.decode('utf-8-sig'))))

def _text(files, suffix):
    matches = [v.decode('utf-8-sig', 'replace') for k,v in files.items() if k.lower().endswith(suffix.lower())]
    return matches[0] if matches else ''

def _rows(files, suffix):
    rows=[]
    for k,v in files.items():
        if k.lower().endswith(suffix.lower()):
            try: rows.extend(_csv(v))
            except Exception: pass
    return rows

def _words(s): return len(s.split())

def _fit(text, limit):
    words = re.findall(r"\S+", text.strip())
    if len(words) <= limit: return text.strip()
    return ' '.join(words[:max(1, limit-1)]) + '…'

def _openai_polish_pass(text, api_key='', model='gpt-4.1-mini'):
    key=(api_key or os.environ.get('OPENAI_API_KEY','')).strip()
    if not key: raise ValueError('OpenAI polishing is enabled, but no API key was provided. Enter an OpenAI API key or turn off answer polishing.')
    payload=json.dumps({
        'model':model or 'gpt-4.1-mini',
        'store':False,
        'instructions':'Polish this nonprofit grant application answer so it reads naturally, clearly, and warmly in an authentic human voice. Preserve every fact, number, date, commitment, qualification, and uncertainty exactly. Do not add evidence, outcomes, people, services, or claims. Do not mention AI or detection. Return only the revised answer.',
        'input':text
    }).encode('utf-8')
    req=Request('https://api.openai.com/v1/responses',data=payload,headers={'Authorization':f'Bearer {key}','Content-Type':'application/json'},method='POST')
    try:
        with urlopen(req,timeout=90) as response: result=json.loads(response.read().decode('utf-8'))
    except HTTPError as e:
        detail=e.read().decode('utf-8','replace')[:500]
        raise ValueError(f'OpenAI API returned HTTP {e.code}: {detail}')
    except (URLError, TimeoutError) as e: raise ValueError(f'Could not connect to the OpenAI API: {e}')
    rewritten='\n'.join(part.get('text','') for item in result.get('output',[]) if item.get('type')=='message' for part in item.get('content',[]) if part.get('type')=='output_text')
    if not rewritten.strip(): raise ValueError('OpenAI did not return a text answer. Check the model name and API project access.')
    return rewritten.strip()

def _validation_grants(include_documents=False):
    path=Path(__file__).resolve().parent/'validation_grants.csv'
    with path.open('r',encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
    for row in rows:
        row['annual_amount']=_num(row,'annual_amount')
        row['current_quarter_budget']=_num(row,'current_quarter_budget')
        row['current_quarter_spend']=_num(row,'current_quarter_spend')
        row['total_to_date']=_num(row,'total_to_date')
        row['work_progress']=_num(row,'work_progress')
        budget=row['current_quarter_budget']; spend=row['current_quarter_spend']
        row['budget_use_pct']=spend/budget if budget else 0
        row['risk_band']=_risk_band(row['budget_use_pct']) if budget else 'unknown'
        row['current_quarter_balance']=budget-spend
        group={'APPLYING':'applying','APPROVED':'approved','COMPLETED':'completed'}.get(row.get('status'),'')
        directory=Path(__file__).resolve().parent/'validation_documents'/group/row['validation_id']
        document_paths=sorted(directory.glob('*')) if directory.is_dir() else []
        row['document_count']=len([p for p in document_paths if p.is_file()])
        if include_documents:
            row['documents']=[{'name':p.name,'url':f"/validation-documents/{row['validation_id']}/{p.name}"} for p in document_paths if p.is_file()]
    return rows

SPEND_MIX = [
    ('Children & mentoring', '#57A6D8'),
    ('Family support', '#55A77B'),
    ('School safety', '#E0B642'),
    ('Mental health', '#9A78C5'),
    ('Staff, materials & evaluation', '#E58C54'),
]

def _spend_mix_weights(label):
    text=str(label or '').casefold()
    school=any(x in text for x in ('school','workshop','safety','classroom','education'))
    mental=any(x in text for x in ('mental health','wellness','behavioral','behavior','therap','clinical'))
    if any(x in text for x in ('child','youth','mentor','student','teen')): return {0:1.0}
    if any(x in text for x in ('family','caregiver','parent','transport','counsel')): return {1:1.0}
    if school and mental: return {2:0.5,3:0.5}
    if mental: return {3:1.0}
    if school: return {2:1.0}
    return {4:1.0}

def _spending_forecast(expenses, budgets, today):
    current_year=today.year
    years=(current_year-1,current_year,current_year+1)
    actual=defaultdict(lambda:defaultdict(float))
    for row in expenses:
        dt=_date(row.get('date') or row.get('transaction_date') or row.get('expense_date') or row.get('month'))
        if not dt: continue
        amount=_num(row,'amount','amount_usd','actual_amount','actual_expense','spent')
        label=' '.join(str(row.get(k,'') or '') for k in ('funder_budget_category','quickbooks_category','category','description'))
        for idx,weight in _spend_mix_weights(label).items(): actual[dt.year][idx]+=amount*weight
    budget=defaultdict(lambda:defaultdict(float))
    for row in budgets:
        amount=_num(row,'approved_amount','approved_amount_usd','budget_amount','amount','approved_budget')
        if amount<=0: continue
        label=row.get('funder_budget_category') or row.get('budget_category') or row.get('category') or row.get('quickbooks_category') or ''
        start=_date(row.get('grant_start') or row.get('grant_start_date') or row.get('budget_period_start') or row.get('period_start') or row.get('start_date'))
        end=_date(row.get('grant_end') or row.get('grant_end_date') or row.get('budget_period_end') or row.get('period_end') or row.get('end_date'))
        year_value=str(row.get('calendar_year') or row.get('budget_year') or row.get('year') or '').strip()
        year_match=re.fullmatch(r'(?:CY\s*)?(20\d{2})',year_value,re.I) if year_value else None
        explicit_year=int(year_match.group(1)) if year_match else None
        weights=_spend_mix_weights(label)
        if year_value:
            if explicit_year in years:
                for idx,weight in weights.items(): budget[explicit_year][idx]+=amount*weight
            continue
        elif start and end:
            if end<start: continue
            duration=(end-start).days+1
            for year in years:
                overlap_start=max(start,date(year,1,1)); overlap_end=min(end,date(year,12,31))
                if overlap_end<overlap_start: continue
                share=amount*((overlap_end-overlap_start).days+1)/duration
                for idx,weight in weights.items(): budget[year][idx]+=share*weight
        else:
            for idx,weight in weights.items(): budget[current_year][idx]+=amount*weight
    def values_for(year, source):
        return [max(0.0,source.get(year,{}).get(i,0.0)) for i in range(len(SPEND_MIX))]
    last_actual=values_for(current_year-1,actual)
    this_budget=values_for(current_year,budget)
    this_projection=this_budget
    if sum(this_budget)>0:
        current_basis='Budget-based estimate using approved budget amounts allocated to this calendar year. Grant dates determine allocation; undated budget rows stay in this year.'
    else:
        current_basis='No approved budget was allocated to this calendar year; the budget-based estimate is zero.'
    next_budget=values_for(current_year+1,budget)
    next_projection=next_budget
    if sum(next_budget)>0:
        next_basis='Budget-based forecast using approved budget amounts whose grant terms overlap next calendar year.'
    else:
        next_basis='No approved budget overlaps next calendar year; the budget-based forecast is zero.'
    def chart(year, values, basis, kind):
        total=sum(values)
        return {'year':year,'kind':kind,'basis':basis,'total':round(total,2),'categories':[{'category':SPEND_MIX[i][0],'amount':round(values[i],2),'percent':(values[i]/total if total else 0),'color':SPEND_MIX[i][1]} for i in range(len(SPEND_MIX))]}
    return [
        chart(current_year-1,last_actual,'Uploaded expense actuals for this calendar year.','Actual'),
        chart(current_year,this_projection,current_basis,'Budget estimate'),
        chart(current_year+1,next_projection,next_basis,'Budget forecast'),
    ]

def _num(row, *keys):
    for k in keys:
        try: return float(str(row.get(k, '')).replace('$','').replace(',','').strip())
        except (ValueError, TypeError): pass
    return 0.0

def _xlcol(index):
    result=''
    while True:
        index,rem=divmod(index,26); result=chr(65+rem)+result
        if index==0: return result
        index-=1

def _risk_band(ratio, threshold=0.85):
    if ratio is None: return 'unknown'
    if ratio > 1.10: return 'high'
    if ratio > 1.0: return 'over'
    if ratio >= threshold: return 'near'
    return 'within'

def _date(s):
    for fmt in ('%Y-%m-%d','%m/%d/%Y','%m/%d/%y'):
        try: return datetime.strptime(str(s)[:10], fmt).date()
        except ValueError: pass
    return None

def _read_zip(blob):
    try: z=zipfile.ZipFile(io.BytesIO(blob))
    except Exception: raise ValueError('Unable to read the ZIP file. Upload a package containing grant folders and source files.')
    files={}; total=0
    for info in z.infolist():
        p=PurePosixPath(info.filename)
        if info.is_dir() or info.filename.startswith('__MACOSX/') or '..' in p.parts or p.is_absolute(): continue
        total += info.file_size
        if total > MAX_UNCOMPRESSED: raise ValueError('The uncompressed package exceeds the 150 MB limit.')
        if info.file_size <= 15*1024*1024: files[info.filename]=z.read(info)
    if not files: raise ValueError('The ZIP contains no readable files.')
    return files

def _fiscal_year(day, start_month):
    if not day: return ''
    y = day.year + (1 if day.month >= start_month else 0)
    return f'FY{y}'

def _month_start_from_funder(files, grant_id):
    months={'january':1,'october':10,'july':7,'jan':1,'oct':10,'jul':7}
    for path,data in files.items():
        if path.lower().endswith('funder_requirements.csv'):
            for row in _csv(data):
                if row.get('grant_id')==grant_id:
                    month=int(_num(row,'fiscal_year_start_month','fiscal_start_month'))
                    if month in (1,7,10): return month
    for path,data in files.items():
        if path.lower().endswith('funder_requirements.md'):
            text=data.decode('utf-8-sig','replace')
            if grant_id.lower() in text.lower():
                match=re.search(r'funder fiscal year:\s*(January|October|July|Jan|Oct|Jul)\s+\d{1,2}',text,re.I)
                if match: return months[match.group(1).lower()]
    for path,data in files.items():
        if path.lower().endswith('.csv'):
            try: rows=_csv(data)
            except Exception: continue
            for row in rows:
                if row.get('grant_id')!=grant_id: continue
                value=' '.join(str(row.get(k,'')) for k in ('funder_fiscal_year','fiscal_year','fiscal_year_start','fiscal_year_start_date'))
                match=re.search(r'\b(January|October|July|Jan|Oct|Jul)\b',value,re.I)
                if match: return months[match.group(1).lower()]
    return None

def _quarter_close_dates(today, start_month):
    anchor_year=today.year if today.month>=start_month else today.year-1
    dates=[]
    for fyyear in range(anchor_year-1,anchor_year+3):
        for quarter in range(1,5):
            absolute=fyyear*12+(start_month-1)+quarter*3
            d=date(absolute//12,absolute%12+1,1)
            if d>=today: dates.append((d,quarter))
    return sorted(dates)[:4]

def _ics_escape(value):
    return str(value).replace('\\','\\\\').replace(';','\\;').replace(',','\\,').replace('\n','\\n')

def _calendar(reminders):
    lines=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//Tidepath Grant Desk//Quarterly Grant Reminders//EN','CALSCALE:GREGORIAN','METHOD:PUBLISH']
    first_by_grant={}
    for row in reminders: first_by_grant.setdefault(row['grant_id'],row)
    for gid,row in first_by_grant.items():
        start=row['close_reminder_date'].replace('-','')+'T090000'
        lines += ['BEGIN:VEVENT',f'UID:{_ics_escape(gid)}-quarter-close@tidepath.local',f'DTSTAMP:{datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")}',f'DTSTART:{start}','DURATION:PT15M','RRULE:FREQ=MONTHLY;INTERVAL=3',f'SUMMARY:{_ics_escape("Quarterly grant ledger close — "+row["funder"])}',f'DESCRIPTION:{_ics_escape("Rebuild this grant’s spending spreadsheet from uploaded receipts and ledger records. Reconcile categories to the award budget and send exceptions to the bookkeeper.")}','END:VEVENT']
    lines.append('END:VCALENDAR')
    return '\r\n'.join(lines)+'\r\n'

def _narrative(files, grant_id, grant_name, limit_rows, fact_sheet, req_text, use_openai=False, openai_api_key='', openai_model='gpt-4.1-mini'):
    folder=''
    for path,data in files.items():
        if path.lower().endswith(('award_budget.csv','budget.csv')):
            try:
                if any(r.get('grant_id')==grant_id for r in _csv(data)):
                    folder=str(PurePosixPath(path).parent); break
            except Exception: pass
    ref = next((v.decode('utf-8-sig','replace') for k,v in files.items() if k.lower().endswith(('application_draft.md','proposal_reference.md','proposal.md')) and (not folder or str(PurePosixPath(k).parent)==folder)), '')
    base = re.sub(r'[#*_`>]', '', ref or fact_sheet)
    base = re.sub(r'\s+', ' ', base).strip()
    source_sections={}
    headings=list(re.finditer(r'^##\s+(.+?)\s*$',ref,re.M))
    for i,h in enumerate(headings):
        block=ref[h.end():headings[i+1].start() if i+1<len(headings) else len(ref)]
        response=re.search(r'\*\*Response(?:\s+\([^)]*\))?:\*\*\s*(.*?)(?=\n##\s|\Z)',block,re.S)
        if response: source_sections[h.group(1).split('(')[0].strip().casefold()]=re.sub(r'\s+',' ',response.group(1)).strip()
    questions = []
    for row in limit_rows:
        if row.get('grant_id') and row.get('grant_id') != grant_id: continue
        prompt=row.get('question_text') or row.get('funder_question') or row.get('question') or row.get('field') or row.get('narrative_field') or row.get('field_name') or row.get('section') or ''
        title=row.get('field_name') or row.get('question_title') or row.get('section') or re.split(r'[?.!]',prompt,maxsplit=1)[0][:90] or prompt
        lookup=row.get('field_name') or row.get('question') or title
        questions.append((title,prompt,int(_num(row,'max_words','word_limit','limit','maximum','maximum_words')),lookup))
    if not questions:
        questions=[(x,x,250,x) for x in ['Statement of Goals','Implementation','Outreach & Engagement','Assessment','Qualifications & Sustainability','Advancing Equity','Financial Narrative']]
    lines=[f'# Application narrative draft — {grant_name}', '', '> Draft generated from uploaded materials marked staff-approved for this run. Confirm the source trail and funder instructions before submission.', '']
    answers=[]
    for title,prompt,limit,lookup in questions:
        if limit <= 0: limit = 250
        search=(lookup or title).casefold()
        section = source_sections.get(search) or next((v for k,v in source_sections.items() if search in k or k in search), '')
        if not section: section=f'{prompt}: {base}' if prompt else base
        section = _fit(section, limit)
        if use_openai:
            for _ in range(3):
                section=_fit(_openai_polish_pass(section,api_key=openai_api_key,model=openai_model),limit)
        lines += [f'## {title or "Narrative response"}', '', f'**Funder question:** {prompt or title}', '', '**Answer:**', '', section, '', f'*Word count: {_words(section)} / {limit}*', '']
        answers.append({'title':title or 'Narrative response','question':prompt or title,'answer':section,'word_count':_words(section),'word_limit':limit})
    return '\n'.join(lines),answers

def _workbook(portfolio, spends, limits, queue, reminders, settlements, validation_grants=(), data_is_synthetic=False):
    out=io.BytesIO(); wb=Workbook(out, {'in_memory':True}); header=wb.add_format({'bold':True,'bg_color':'#DCEAF7','border':1,'text_wrap':True}); money=wb.add_format({'num_format':'$#,##0.00'}); pct=wb.add_format({'num_format':'0.0%'}); title=wb.add_format({'bold':True,'font_size':18,'font_color':'#17365D'}); red=wb.add_format({'bg_color':'#E35B5B','font_color':'#FFFFFF'}); orange=wb.add_format({'bg_color':'#F4A261','font_color':'#7C2D12'}); yellow=wb.add_format({'bg_color':'#FFE066','font_color':'#6B5300'}); green=wb.add_format({'bg_color':'#D8F3DC','font_color':'#315C3B'})
    def sheet(name, rows, fields, money_fields=(), percent_fields=()):
        ws=wb.add_worksheet(name); ws.freeze_panes(1,0); ws.autofilter(0,0,len(rows),len(fields)-1)
        for c,f in enumerate(fields): ws.write(0,c,f,header); ws.set_column(c,c, min(36,max(14,len(f)+3)))
        for r,row in enumerate(rows,1):
            for c,f in enumerate(fields):
                val=row.get(f,'')
                if f in money_fields: ws.write_number(r,c,float(val or 0),money)
                elif f in percent_fields and val not in ('',None): ws.write_number(r,c,float(val),pct)
                else: ws.write(r,c,val)
        status_field=next((f for f in ('status','reconciliation_status') if f in fields),None)
        if rows and status_field:
            c=fields.index(status_field); rg=f'{_xlcol(c)}2:{_xlcol(c)}{len(rows)+1}'
            if 'risk_band' in fields:
                bandcol=_xlcol(fields.index('risk_band'))
                for band,fmt in (('high',red),('over',orange),('near',yellow),('within',green)):
                    ws.conditional_format(rg,{'type':'formula','criteria':f'=${bandcol}2="{band}"','format':fmt})
            else:
                ws.conditional_format(rg,{'type':'text','criteria':'containing','value':'SIGNIFICANT','format':red})
                ws.conditional_format(rg,{'type':'text','criteria':'containing','value':'OVER BUDGET','format':orange})
                ws.conditional_format(rg,{'type':'text','criteria':'containing','value':'RISK','format':yellow})
                ws.conditional_format(rg,{'type':'text','criteria':'containing','value':'TRACK','format':green})
        if rows and 'utilization' in fields:
            c=fields.index('utilization'); ws.conditional_format(1,c,len(rows),c,{'type':'data_bar','bar_color':'#59A88D'})
        if name=='Validation Grants' and rows:
            status_index=fields.index('status'); statuscol=_xlcol(status_index)
            ws.conditional_format(1,status_index,len(rows),status_index,{'type':'formula','criteria':f'=${statuscol}2="APPLYING"','format':wb.add_format({'bg_color':'#EAF4FC','font_color':'#245675'})})
            ws.conditional_format(1,status_index,len(rows),status_index,{'type':'formula','criteria':f'=${statuscol}2="COMPLETED"','format':wb.add_format({'bg_color':'#ECEFF0','font_color':'#657176'})})
        if not rows: ws.write(1,0,'No records found')
    dashboard=wb.add_worksheet('Dashboard'); dashboard.hide_gridlines(2); dashboard.set_column('A:A',25); dashboard.set_column('B:D',18); dashboard.set_column('E:E',5); dashboard.set_column('F:N',13)
    dashboard.write('A1','GRANT PORTFOLIO · AT A GLANCE',title)
    if data_is_synthetic: dashboard.merge_range('A2:N2','SYNTHETIC / FICTIONAL CHALLENGE DATA — NOT REAL AWARDS OR EXPENSES',wb.add_format({'bold':True,'font_color':'#9C0006','bg_color':'#FCE4D6','align':'center'}))
    metrics=[('Active grants',len(portfolio)),('Award budget',sum(x['award_amount'] for x in portfolio)),('Recorded spend',sum(x['actual_spend'] for x in portfolio)),('Over budget categories',sum(x['status'] in ('OVER BUDGET','SIGNIFICANT OVERRUN') for x in spends)),('At risk categories',sum(x['status']=='AT RISK' for x in spends)),('Reports due / overdue',sum(x['status'] in ('OVERDUE','DUE') for x in queue)),('Quarterly close reminders',len(reminders)),('Close lines for review',sum(x['review_items']>0 or x['reconciliation_status'] not in ('READY FOR BOOKKEEPER REVIEW','AT RISK') for x in settlements))]
    for i,(label,value) in enumerate(metrics):
        row=2+(i//4)*3; col=(i%4)*3
        dashboard.merge_range(row,col,row,col+1,label,header)
        fmt=money if isinstance(value,(int,float)) and any(x in label for x in ('budget','spend')) else wb.add_format({'bold':True,'font_size':16,'font_color':'#187861','num_format':'#,##0'})
        dashboard.merge_range(row+1,col,row+1,col+1,value,fmt)
    dashboard.write('A9','Priority actions',header)
    actions=[]
    for x in spends:
        if x['status'] in ('OVER BUDGET','SIGNIFICANT OVERRUN'): actions.append(f"{x['grant_id']} · {x['category']}: over budget by ${abs(x['remaining']):,.2f}; review and document corrective action.")
        elif x['status']=='AT RISK': actions.append(f"{x['grant_id']} · {x['category']}: at {x['utilization']:.0%} of category budget; check remaining commitments.")
    for x in queue:
        if x['status']=='OVERDUE': actions.append(f"{x['grant_id']} · report overdue since {x['report_due']}; complete the draft and verify outcomes.")
    for i,action in enumerate(actions[:8],10): dashboard.merge_range(i-1,0,i-1,12,'• '+action,wb.add_format({'text_wrap':True,'valign':'vcenter','bg_color':'#FFF6E5' if 'over budget' in action or 'overdue' in action else '#F7FAFC'})); dashboard.set_row(i-1,30)
    sheet('Portfolio',portfolio,['grant_id','grant_name','funder','award_amount','actual_spend','remaining','budget_utilization','work_progress','work_data_status','status'],{'award_amount','actual_spend','remaining'},{'budget_utilization','work_progress'})
    sheet('Category Spend',spends,['grant_id','funder','funder_fiscal_year','category','approved_budget','actual_spend','remaining','utilization','risk_band','status'],{'approved_budget','actual_spend','remaining'},{'utilization'})
    sheet('Application Limits',limits,['grant_id','grant_name','question','word_count','word_limit','within_limit'])
    sheet('Report Queue',queue,['grant_id','grant_name','funder','report_due','status','special_circumstances','draft_file'])
    sheet('Grant Reminders',reminders,['grant_id','funder','fiscal_year_start_month','close_reminder_date','quarter','task'])
    sheet('Financial Close',settlements,['grant_id','funder','funder_fiscal_year','quarter','category','transactions','quarter_spend','fy_cumulative_spend','annual_category_budget','remaining_fy_budget','review_items','risk_band','reconciliation_status'],{'quarter_spend','fy_cumulative_spend','annual_category_budget','remaining_fy_budget'})
    sheet('Validation Grants',validation_grants,['validation_id','grant_name','status','funder','annual_amount','current_quarter_budget','current_quarter_spend','current_quarter_balance','budget_use_pct','risk_band','total_to_date','work_progress','completed_on','document_count','scenario','special_note','data_status'],{'annual_amount','current_quarter_budget','current_quarter_spend','current_quarter_balance','total_to_date'},{'budget_use_pct','work_progress'})
    if portfolio:
        palette={'within':'#BDE0FE','near':'#FFE066','over':'#F4A261','high':'#E35B5B','unknown':'#CBD5D1'}
        budget_points=[{'fill':{'color':palette.get(row['risk_band'],'#CBD5D1')}} for row in portfolio]
        work_points=[]
        for row in portfolio:
            progress=row.get('work_progress'); band='unknown' if progress is None else 'within' if progress>=1 else 'near' if progress>=.85 else 'over' if progress>=.60 else 'high'
            work_points.append({'fill':{'color':palette[band]}})
        chart=wb.add_chart({'type':'bar'}); chart.add_series({'name':'Budget used','categories':['Portfolio',1,0,len(portfolio),0],'values':['Portfolio',1,6,len(portfolio),6],'points':budget_points}); chart.add_series({'name':'Work completed','categories':['Portfolio',1,0,len(portfolio),0],'values':['Portfolio',1,7,len(portfolio),7],'points':work_points}); chart.set_title({'name':'Budget use and work progress'}); chart.set_x_axis({'num_format':'0%','max':1}); chart.set_legend({'position':'bottom'}); dashboard.insert_chart('A17',chart,{'x_scale':1.4,'y_scale':1.2})
    if spends:
        colors={'within':'#BDE0FE','near':'#FFE066','over':'#F4A261','high':'#E35B5B','unknown':'#B9C5C2'}
        chart=wb.add_chart({'type':'bar'}); points=[{'fill':{'color':colors.get(row.get('risk_band'),'#B9C5C2')}} for row in spends]; chart.add_series({'name':'Budget utilization','categories':['Category Spend',1,3,len(spends),3],'values':['Category Spend',1,7,len(spends),7],'points':points}); chart.set_title({'name':'Category budget utilization'}); chart.set_x_axis({'num_format':'0%'}); chart.set_legend({'none':True}); dashboard.insert_chart('H17',chart,{'x_scale':1.4,'y_scale':1.2})
    ws=wb.add_worksheet('Read Me'); ws.write(0,0,'Grant portfolio summary workbook',title); ws.write(2,0,'Generated from the uploaded grant ZIP. Check source figures, fiscal-year rules, eligibility, and narrative content before use.'); ws.set_column(0,0,110)
    wb.close(); return out.getvalue()

def process_bundle(blob, as_of, threshold, use_openai=False, openai_api_key='', openai_model='gpt-4.1-mini', facts_approved=False):
    files=_read_zip(blob); fact=_text(files,'organization_fact_sheet.md') or _text(files,'fact_sheet.md')
    if not fact: raise ValueError('Missing organization_fact_sheet.md or fact_sheet.md.')
    if not facts_approved: raise ValueError('Confirm that staff reviewed and approved the facts and proposal passages before generating answers.')
    if not 1 <= threshold <= 100: raise ValueError('The category alert threshold must be between 1 and 100.')
    today=_date(as_of) or date.today(); reqs=_rows(files,'funder_requirements.csv'); budgets=_rows(files,'award_budget.csv'); expenses=_rows(files,'actual_expenses.csv'); limits=_rows(files,'narrative_limits.csv'); reports=_rows(files,'report_schedule.csv'); outcomes=_rows(files,'outcomes_data.csv')
    # Flexible fallback for bundled flat exports.
    if not budgets: budgets=_rows(files,'budget.csv')
    if not expenses: expenses=_rows(files,'monthly_budget_actuals.csv')
    if not reports: reports=_rows(files,'report_queue.csv')
    if not limits: limits=_rows(files,'application_word_count_review.csv')
    grant_map={}
    for r in budgets:
        gid=r.get('grant_id') or r.get('grant') or ''; grant_map.setdefault(gid,{'grant_id':gid,'grant_name':r.get('grant_name') or gid,'funder':r.get('funder') or r.get('funder_name') or r.get('mock_funder',''),'budget':0,'special_circumstances':[]})
        grant_map[gid]['budget'] += _num(r,'approved_amount','approved_amount_usd','budget_amount','amount','approved_budget')
        for field in ('restriction_summary','special_circumstances','known_issues','data_status'):
            note=str(r.get(field,'')).strip()
            if note and note not in grant_map[gid]['special_circumstances']: grant_map[gid]['special_circumstances'].append(note)
    spends=defaultdict(float); approved=defaultdict(float); category_rows=[]; quarterly=defaultdict(lambda:{'amount':0.0,'transactions':0,'review_items':0})
    req_map={r.get('grant_id',''):r for r in reqs}
    for gid in grant_map:
        if gid not in req_map:
            reqtext=next((v.decode('utf-8-sig','replace') for k,v in files.items() if k.lower().endswith('funder_requirements.md') and gid.lower() in v.decode('utf-8-sig','replace').lower()), '')
            m=re.search(r'fiscal year:\s*([A-Za-z]+)\s+\d{1,2}',reqtext,re.I)
            months={'january':1,'february':2,'march':3,'april':4,'may':5,'june':6,'july':7,'august':8,'september':9,'october':10,'november':11,'december':12}
            req_map[gid]={'fiscal_year_start_month':months.get(m.group(1).lower(),10) if m else 10}
    for r in expenses:
        gid=r.get('grant_id') or r.get('grant') or ''; meta=grant_map.setdefault(gid,{'grant_id':gid,'grant_name':r.get('grant_name') or gid,'funder':r.get('funder') or r.get('mock_funder') or '','budget':0,'special_circumstances':[]})
        dt=_date(r.get('date') or r.get('transaction_date') or r.get('expense_date') or r.get('month')); req=req_map.get(gid,{})
        start=int(_num(req,'fiscal_year_start_month') or 0)
        if start not in (1,7,10): start=_month_start_from_funder(files,gid) or 10
        fy=_fiscal_year(dt,start)
        cat=r.get('funder_budget_category') or r.get('category') or r.get('budget_category') or 'Unmapped'
        key=(gid,fy,cat); spends[key]+=_num(r,'actual_amount','actual_spend','amount','amount_usd','expense');
        if key not in approved: approved[key]=_num(r,'approved_amount','approved_amount_usd','approved_budget','category_budget','budget_amount')
        meta['funder']=meta['funder'] or r.get('funder') or r.get('mock_funder','')
        if dt:
            offset=(dt.month-start)%12; quarter=offset//3+1
            qabs=dt.year*12+(dt.month-1)-(offset%3); qyear=qabs//12; qmonth=qabs%12+1; qstart=f'{qyear:04d}-{qmonth:02d}-01'
            qkey=(gid,fy,cat,qstart,quarter); item=quarterly[qkey]; item['amount']+=_num(r,'actual_amount','actual_spend','amount','amount_usd','expense'); item['transactions']+=1
            approval=str(r.get('approval_status','')).casefold(); receipt=str(r.get('supporting_document') or r.get('receipt_or_journal_id') or '').strip()
            if not approval or ('approv' not in approval and approval not in ('paid','cleared')) or not receipt: item['review_items']+=1
            if not approval or ('approv' not in approval and approval not in ('paid','cleared')):
                note=f"Expense approval needs review: {r.get('transaction_id') or r.get('vendor') or 'unnamed transaction'}"
                if note not in meta['special_circumstances']: meta['special_circumstances'].append(note)
            if not receipt:
                note=f"Missing receipt or journal reference: {r.get('transaction_id') or r.get('vendor') or 'unnamed transaction'}"
                if note not in meta['special_circumstances']: meta['special_circumstances'].append(note)
    work_metrics=defaultdict(list)
    for r in outcomes:
        gid=r.get('grant_id',''); target=_num(r,'target','target_value'); actual=_num(r,'actual','actual_value','actual_result','synthetic_actual','value')
        if gid and target>0:
            work_metrics[gid].append(max(0,min(1,actual/target)))
            meta=grant_map.setdefault(gid,{'grant_id':gid,'grant_name':gid,'funder':'','budget':0,'special_circumstances':[]})
            if 'synthetic' in str(r.get('data_status','')).casefold() and 'Synthetic outcome figures; not verified' not in meta['special_circumstances']:
                meta['special_circumstances'].append('Synthetic outcome figures; not verified')
    for gid,m in grant_map.items():
        if work_metrics.get(gid):
            m['work_progress']=sum(work_metrics[gid])/len(work_metrics[gid])
            m['work_data_status']='DEMO ONLY' if any('synthetic outcome' in note.casefold() for note in m['special_circumstances']) else 'REPORTED — VERIFY SOURCE'
        else: m['work_progress']=None; m['work_data_status']='NO OUTCOME DATA'
    for r in budgets:
        gid=r.get('grant_id') or r.get('grant') or ''; req=req_map.get(gid,{}); start=int(_num(req,'fiscal_year_start_month') or 0)
        if start not in (1,7,10): start=_month_start_from_funder(files,gid) or 10
        fy=r.get('funder_fiscal_year') or r.get('fiscal_year') or ''
        if not re.match(r'^(FY)?\d{4}', str(fy), re.I): fy=_fiscal_year(_date(r.get('period_start') or r.get('date') or r.get('grant_start')),start)
        category=r.get('funder_budget_category') or r.get('category') or r.get('budget_category') or ''
        if category: approved[(gid,fy,category)]+=_num(r,'approved_amount','approved_amount_usd','budget_amount','amount','approved_budget')
    for key,amount in spends.items():
        gid,fy,cat=key; budget=approved[key]; remain=budget-amount; util=amount/budget if budget else 0
        status='SIGNIFICANT OVERRUN' if budget and util>1.10 else 'OVER BUDGET' if budget and util>1.0 else 'AT RISK' if budget and util>=threshold/100 else 'ON TRACK' if budget else 'BUDGET NOT MAPPED'
        band=_risk_band(util if budget else None,threshold/100)
        category_rows.append(dict(grant_id=gid,funder=grant_map.get(gid,{}).get('funder',''),funder_fiscal_year=fy,category=cat,approved_budget=budget,actual_spend=amount,remaining=remain,utilization=util,risk_band=band,status=status))
        if status in ('OVER BUDGET','SIGNIFICANT OVERRUN'):
            note=f"{status}: {cat} is over its approved category budget by ${abs(remain):,.2f}"
            if note not in grant_map.get(gid,{}).get('special_circumstances',[]): grant_map[gid]['special_circumstances'].append(note)
    quarterly_close=[]; cumulative=defaultdict(float)
    for (gid,fy,cat,qstart,quarter),item in sorted(quarterly.items(),key=lambda x:(x[0][0],x[0][1],x[0][2],x[0][3])):
        ckey=(gid,fy,cat); cumulative[ckey]+=item['amount']; budget=approved.get(ckey,0.0); remaining=budget-cumulative[ckey]
        utilization=cumulative[ckey]/budget if budget else 0
        rec_status='BUDGET NOT MAPPED' if not budget else 'SIGNIFICANT OVERRUN' if utilization>1.10 else 'OVER BUDGET' if utilization>1.0 else 'AT RISK' if utilization>=threshold/100 else 'READY FOR BOOKKEEPER REVIEW'
        quarterly_close.append(dict(grant_id=gid,funder=grant_map.get(gid,{}).get('funder',''),funder_fiscal_year=fy,quarter=f'Q{quarter} · {qstart}',category=cat,transactions=item['transactions'],quarter_spend=item['amount'],fy_cumulative_spend=cumulative[ckey],annual_category_budget=budget,remaining_fy_budget=remaining,review_items=item['review_items'],risk_band=_risk_band(utilization if budget else None,threshold/100),reconciliation_status=rec_status))
    portfolio=[]
    for gid,m in grant_map.items():
        subset=[x for x in category_rows if x['grant_id']==gid]; actual=sum(x['actual_spend'] for x in subset); budget=m['budget'] or sum(x['approved_budget'] for x in subset); remaining=budget-actual
        utilization=actual/budget if budget else 0
        status='SIGNIFICANT OVERRUN' if budget and utilization>1.10 else 'OVER BUDGET' if budget and utilization>1 else 'AT RISK' if budget and utilization>=threshold/100 else 'ON TRACK' if budget else 'BUDGET NOT MAPPED'
        portfolio.append(dict(grant_id=gid,grant_name=m['grant_name'],funder=m['funder'],award_amount=budget,actual_spend=actual,remaining=remaining,budget_utilization=utilization if budget else None,work_progress=m.get('work_progress'),work_data_status=m.get('work_data_status','NO OUTCOME DATA'),risk_band=_risk_band(utilization if budget else None,threshold/100),status=status))
    reminders=[]
    for gid,m in grant_map.items():
        start=int(_num(req_map.get(gid,{}),'fiscal_year_start_month') or 0)
        if start not in (1,7,10): start=_month_start_from_funder(files,gid) or 10
        for close_date,quarter in _quarter_close_dates(today,start):
            reminders.append(dict(grant_id=gid,funder=m.get('funder',''),fiscal_year_start_month=start,close_reminder_date=close_date.isoformat(),quarter=f'Q{quarter}',task='Rebuild grant spending spreadsheet; reconcile ledger categories, receipts and award budget'))
    ics_content=_calendar(reminders)
    applications=[]; app_files={}; application_groups=[]; by_grant=defaultdict(list)
    for row in limits: by_grant[row.get('grant_id','')].append(row)
    for gid,m in grant_map.items():
        narrative,answers=_narrative(files,gid,m['grant_name'],by_grant.get(gid,limits),fact,_text(files,'funder_requirements.md'),use_openai,openai_api_key,openai_model); app_files[f'applications/{gid or "grant"}-application-draft.md']=narrative
        application_groups.append({'grant_id':gid,'grant_name':m['grant_name'],'funder':m['funder'],'answers':answers})
        for answer in answers:
            applications.append(dict(grant_id=gid,grant_name=m['grant_name'],question=answer['title'],word_count=answer['word_count'],word_limit=answer['word_limit'],within_limit='Within limit' if answer['word_count']<=answer['word_limit'] else 'Over limit'))
    queue=[]; report_files={}
    for r in reports:
        gid=r.get('grant_id') or r.get('grant') or ''; due=_date(r.get('report_due') or r.get('due_date')); status='NOT DUE' if due and due>today else 'OVERDUE' if due else (r.get('status') or r.get('due_status') or 'DUE DATE MISSING')
        if due and due<=today:
            m=grant_map.get(gid,{'grant_name':gid,'funder':''}); spend=sum(x['actual_spend'] for x in category_rows if x['grant_id']==gid)
            label='SYNTHETIC SAMPLE — ' if 'synthetic' in fact.lower() or 'fictional' in fact.lower() else ''
            circumstances=list(m.get('special_circumstances',[])); row_note=str(r.get('special_circumstances') or r.get('known_issues') or '').strip()
            if row_note and row_note not in circumstances: circumstances.append(row_note)
            special_text='\n'.join(f'- {note}' for note in circumstances) if circumstances else '- None recorded in uploaded grant files.'
            content=f"# Grant report draft — {m['grant_name']}\n\n> {label}Draft only. Verify service records, participant counts, outcomes, and financial figures before submission.\n\n- Funder: {m['funder']}\n- Reporting period: {r.get('reporting_period','See award terms')}\n- Due date: {due.isoformat()}\n- Expenditure recorded in uploaded ledger: ${spend:,.2f}\n\n## Special circumstances and restrictions\n{special_text}\n\n## Activities and outcomes\n[Add verified activities, participant reach, outcome data, and any approved changes.]\n\n## Financial narrative\n[Explain category variances and reconcile to the funder-approved budget.]\n"
            fname=f'reports/{gid or "grant"}-report-draft.md'; report_files[fname]=content
        else: fname=''
        m=grant_map.get(gid,{})
        circumstances=list(m.get('special_circumstances',[])); row_note=str(r.get('special_circumstances') or r.get('known_issues') or r.get('data_status') or '').strip()
        if row_note and row_note not in circumstances: circumstances.append(row_note)
        queue.append(dict(grant_id=gid,grant_name=m.get('grant_name',gid),funder=r.get('funder') or r.get('mock_funder') or m.get('funder',''),report_due=due.isoformat() if due else r.get('report_due',''),status=status,special_circumstances='; '.join(circumstances),draft_file=fname))
    data_is_synthetic=any(word in fact.casefold() for word in ('synthetic','fictional','mock','made-up'))
    validation_grants=_validation_grants()
    workbook=_workbook(portfolio,category_rows,applications,queue,reminders,quarterly_close,validation_grants,data_is_synthetic)
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('grant-summary.xlsx',workbook)
        for name,content in app_files.items(): z.writestr(name,content)
        for name,content in report_files.items(): z.writestr(name,content)
        for name,rows in [('portfolio.csv',portfolio),('category_spend.csv',category_rows),('application_limits.csv',applications),('report_queue.csv',queue),('grant_reminders.csv',reminders),('financial_close.csv',quarterly_close),('validation_grants.csv',validation_grants)]:
            s=io.StringIO(); fields=list(rows[0]) if rows else ['status']; w=csv.DictWriter(s,fieldnames=fields); w.writeheader(); w.writerows(rows); z.writestr('csv/'+name,s.getvalue())
        validation_root=Path(__file__).resolve().parent/'validation_documents'
        for doc in sorted(validation_root.rglob('*')):
            if doc.is_file(): z.writestr(f"validation_documents/{doc.relative_to(validation_root).as_posix()}",doc.read_bytes())
        z.writestr('grant-bookkeeper-reminders.ics',ics_content)
        z.writestr('README.md','# Grant analysis output\n\nContains the summary workbook (including quarterly Financial Close and Grant Reminders tabs), application draft narratives, due report drafts, CSV exports, and a recurring quarterly bookkeeper calendar file. The financial close is a budget-to-uploaded-ledger reconciliation for bookkeeper review; it is not a bank reconciliation or posted accounting entry. Generated from uploaded files. Review facts, source records and amounts before submission or reporting.\n')
    summary={'grants':len(portfolio),'award_total':round(sum(x['award_amount'] for x in portfolio),2),'spend_total':round(sum(x['actual_spend'] for x in portfolio),2),'over_budget_categories':sum(x['status'] in ('OVER BUDGET','SIGNIFICANT OVERRUN') for x in category_rows),'at_risk_categories':sum(x['status']=='AT RISK' for x in category_rows),'reports_due':sum(x['status'] in ('OVERDUE','DUE') for x in queue),'applications':len(app_files),'quarterly_reminders':len(reminders),'financial_close_rows':len(quarterly_close),'close_rows_needing_review':sum(x['review_items']>0 or x['reconciliation_status']!='READY FOR BOOKKEEPER REVIEW' for x in quarterly_close)}
    warnings=[]
    if not expenses: warnings.append('No expense details were found. The spend and quarterly-close views will be empty; include actual_expenses.csv or an equivalent transaction file.')
    if not budgets: warnings.append('No award budget was found. Category budgets will be marked as unmapped.')
    if not reports: warnings.append('No report schedule was found. The report queue will be empty.')
    if not any(_month_start_from_funder(files,gid) for gid in grant_map): warnings.append('No July, October, or January fiscal-year start month was identified. Quarterly reminders default to October; set fiscal_year_start_month to 7, 10, or 1 in funder_requirements.csv.')
    if data_is_synthetic: warnings.append('This package contains synthetic, fictional, or mock-data labels. Treat all award, expense, and outcome values as demonstration data, not verified records.')
    actions=[]
    for x in category_rows:
        if x['status'] in ('OVER BUDGET','SIGNIFICANT OVERRUN'): actions.append({'priority':'urgent','title':f"{x['grant_id']} · Category overspend",'detail':f"{x['category']} is ${abs(x['remaining']):,.2f} over budget. Review new commitments and contact the bookkeeper.",'target':'finance'})
        elif x['status']=='AT RISK': actions.append({'priority':'watch','title':f"{x['grant_id']} · Category approaching limit",'detail':f"{x['category']} is at {x['utilization']:.0%} of budget. Check unpaid commitments.",'target':'finance'})
    for x in queue:
        if x['status']=='OVERDUE': actions.append({'priority':'urgent','title':f"{x['grant_id']} · Report overdue",'detail':f"Due {x['report_due']}. Review the draft, verified outcomes, and expense narrative.",'target':'deadlines'})
        elif x['status']=='NOT DUE' and _date(x.get('report_due')) and 0<=(_date(x['report_due'])-today).days<=30: actions.append({'priority':'watch','title':f"{x['grant_id']} · Report due soon",'detail':f"Due {x['report_due']}. Allow time to verify outcomes and spending.",'target':'deadlines'})
    for x in reminders:
        if 0<=(_date(x['close_reminder_date'])-today).days<=14:
            actions.append({'priority':'watch','title':f"{x['grant_id']} · Quarterly close approaching",'detail':f"{x['close_reminder_date']}: rebuild the spending spreadsheet and reconcile funder categories.",'target':'deadlines'})
    for x in quarterly_close:
        if x['review_items'] or x['reconciliation_status'] not in ('READY FOR BOOKKEEPER REVIEW','AT RISK'): actions.append({'priority':'watch','title':f"{x['grant_id']} · Financial close needs review",'detail':f"{x['quarter']} · {x['category']}: {x['review_items']} receipt/approval items need review; status: {x['reconciliation_status']}.",'target':'finance'})
    actions=sorted(actions,key=lambda x:0 if x['priority']=='urgent' else 1)[:16]
    operations={'portfolio':portfolio,'categories':category_rows,'queue':queue,'reminders':reminders,'settlements':quarterly_close,'actions':actions,'application_groups':application_groups,'validation_grants':_validation_grants(include_documents=True),'spending_forecast':_spending_forecast(expenses,budgets,today)}
    return {'summary':summary,'warnings':warnings,'workbook':workbook,'package':out.getvalue(),'ics':ics_content.encode('utf-8'),'previews':[{'name':name.split('/')[-1],'text':content} for name,content in app_files.items()],'operations':operations}
