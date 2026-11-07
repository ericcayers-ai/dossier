import {useEffect,useMemo,useState} from 'react';
import type {ReactNode} from 'react';
import {api} from '../lib/api';
import {useLoad} from '../lib/useLoad';
import {EmptyState,ErrorState,Loading} from './StateViews';
import {count,isOne} from '../lib/copy';

type Tab='jobs'|'pipeline'|'due'|'ranked'|'feeds';
type Payload={kind:Tab;data:any};

const TAB_LABEL:Record<Tab,string>={jobs:'Jobs',pipeline:'Pipeline',due:'Due',ranked:'Ranked',feeds:'Feeds'};

/* A corpus is 500 to 2,000 rows. Rendering all of them turns the pane into 172 KB of
   text and makes the one row that matters unreachable, so the table pages in blocks
   of fifty and says what it is showing. */
const PAGE=50;

/** Filter and sort state survives a pane switch; panes are conditionally mounted. */
function useSticky(key:string,initial:string){
  const [value,setValue]=useState(()=>{try{return sessionStorage.getItem(`dossier-ui:${key}`)??initial}catch{return initial}});
  useEffect(()=>{try{sessionStorage.setItem(`dossier-ui:${key}`,value)}catch{/* ignore */}},[key,value]);
  return [value,setValue] as const;
}

export default function JobsPane():ReactNode{
  const [tab,setTab]=useState<Tab>('jobs');
  const [overdue,setOverdue]=useState(false);
  const [shown,setShown]=useState(PAGE);
  const [query,setQuery]=useSticky('jobs-query','');
  const [fit,setFit]=useSticky('jobs-fit','all');
  const [sort,setSort]=useState<{key:string;direction:1|-1}|null>(null);

  /* A new filter starts its own page count, or "showing 300 of 12" lies. */
  useEffect(()=>{setShown(PAGE)},[tab,query,fit]);

  const loaded=useLoad<Payload>(async()=>{
    if(tab==='jobs')return {kind:tab,data:await api.jobs()};
    if(tab==='pipeline')return {kind:tab,data:{rows:await api.history(),summary:await api.track()}};
    if(tab==='due')return {kind:tab,data:{rows:await api.due(),cadence:await api.cadence(overdue)}};
    if(tab==='ranked')return {kind:tab,data:await api.corpus()};
    return {kind:tab,data:await api.feeds()};
  },[tab,overdue]);

  const jobs:any[]=loaded.state.status==='ready'&&loaded.state.data.kind==='jobs'?loaded.state.data.data:[];
  const filtered=useMemo(()=>{
    const needle=query.trim().toLowerCase();
    const list=jobs.filter(job=>{
      if(fit!=='all'&&(job.fit||'')!==fit)return false;
      if(!needle)return true;
      return [job.title,job.employer,job.company,job.location,job.source].filter(Boolean).join(' ').toLowerCase().includes(needle);
    });
    if(!sort)return list;
    const direction=sort.direction;
    return [...list].sort((left,right)=>{
      const a=String(left[sort.key]??'');
      const b=String(right[sort.key]??'');
      return a.localeCompare(b,undefined,{numeric:true,sensitivity:'base'})*direction;
    });
  },[jobs,query,fit,sort]);
  const fitChips=useMemo(()=>['all','High','Medium','Low','Skip'].filter(value=>value==='all'||jobs.some(job=>(job.fit||'')===value)),[jobs]);
  const counts=loaded.state.status==='ready'?loaded.state.data.data:null;
  const countLine=tab==='jobs'
    ?(jobs.length?`Showing ${Math.min(shown,filtered.length)} of ${filtered.length}`:'No job records in all_boards_data/all_jobs.json')
    :tab==='pipeline'?(counts?.rows?.length?`${counts.rows.length} tracked rows`:'No tracked applications in job-history.md')
    :tab==='due'?(counts?.rows?.length?`${count(counts.rows.length,'row')} ${isOne(counts.rows.length)?'needs':'need'} attention`:'Nothing is due')
    :tab==='ranked'?(counts?.present?`${counts.rows} scored rows`:'No corpus found')
    :(counts?.permitted?`${Object.keys(counts.permitted).length} permitted, ${counts.prohibited?.length??0} prohibited`:'No public boards configured');

  const sortHeader=(key:string,label:string)=><th scope="col" key={key} aria-sort={sort?.key===key?(sort.direction===1?'ascending':'descending'):'none'}>
    <button type="button" onClick={()=>setSort(current=>current?.key===key?{key,direction:current.direction===-1?1:-1}:{key,direction:1})}>{label}{sort?.key===key?(sort.direction===1?' ↑':' ↓'):''}</button>
  </th>;

  return <div className="jobs-pane">
    <div className="audit-head">
      <div>
        <h1>Jobs</h1>
        <p className="pane-purpose">Every job Dossier has saved, plus what you have applied to and what is due a follow-up.</p>
      </div>
    </div>
    <div className="jobs-tabs" role="tablist" aria-label="Job workspace">
      {(['jobs','pipeline','due','ranked','feeds'] as Tab[]).map(value=><button
        type="button" role="tab" id={`jobs-tab-${value}`} aria-controls={`jobs-panel-${value}`}
        aria-selected={tab===value} className={tab===value?'active':''} key={value}
        onClick={()=>setTab(value)}>{TAB_LABEL[value]}</button>)}
    </div>

    <div className="jobs-tools">
      <span className="kbd" role="status" aria-live="polite">{loaded.state.status==='loading'?'Reading…':loaded.state.status==='failed'?'Could not read':countLine}</span>
      {tab==='due'&&<label className="chip"><input type="checkbox" checked={overdue} onChange={event=>setOverdue(event.target.checked)}/> overdue only</label>}
    </div>

    <div role="tabpanel" id={`jobs-panel-${tab}`} aria-labelledby={`jobs-tab-${tab}`} tabIndex={0}>
    {loaded.state.status==='loading'?<Loading what="job records"/>
      :loaded.state.status==='failed'?<ErrorState error={loaded.state.error} what="Reading job records" onRetry={loaded.reload}/>
      :tab==='jobs'?<>
        <div className="jobs-tools">
          <input className="filter" aria-label="Filter jobs" placeholder="e.g. Hamilton" value={query} onChange={event=>setQuery(event.target.value)}/>
          <div className="chips">{fitChips.map(value=><button type="button" key={value} className={`chip ${fit===value?'active':''}`} aria-pressed={fit===value} onClick={()=>setFit(value)}>{value==='all'?'All fits':value}</button>)}</div>
        </div>
        {jobs.length===0?<EmptyState title="No postings archived yet">
          <p>Use <b>Search → Capture</b> to archive a board, then this table fills from the corpus.</p>
        </EmptyState>
          :<div className="table-wrap"><table className="data-table">
            <thead><tr>{sortHeader('fit','Fit')}{sortHeader('title','Role')}{sortHeader('employer','Employer')}{sortHeader('location','Location')}{sortHeader('source','Source')}</tr></thead>
            <tbody>{filtered.slice(0,shown).map((job,index)=><tr key={`${job.id??'row'}-${index}`}><td>{job.fit||'n/a'}</td><td>{job.title||'n/a'}</td><td>{job.employer||job.company||'n/a'}</td><td>{job.location||'n/a'}</td><td>{job.source||'n/a'}</td></tr>)}
            {filtered.length===0&&<tr><td colSpan={5}><div className="empty">No job matches that filter. Clear it to see all {jobs.length}.</div></td></tr>}</tbody>
          </table></div>}
        {filtered.length>shown&&<div className="button-row"><button type="button" onClick={()=>setShown(value=>value+PAGE)}>{`Show ${Math.min(PAGE,filtered.length-shown)} more`}</button></div>}
      </>
      :tab==='pipeline'?<>
        {counts.summary&&<div className="audit-counts">{Object.entries(counts.summary.status_counts??{}).map(([status,value])=><div className="audit-count" key={status}><b>{value as number}</b><span>{status}</span></div>)}</div>}
        {counts.summary?.actionable_without_date?.length>0&&<div className="notice">{count(counts.summary.actionable_without_date.length,'actionable row')} have no confirmed application date, so no follow-up can be dated: {counts.summary.actionable_without_date.join(', ')}.</div>}
        {counts.rows.length===0?<EmptyState title="No applications tracked yet">
          <p>The tracker reads <code>job-history.md</code>. Mark a row <code>drafted</code> and it appears here.</p>
        </EmptyState>
          :<div className="pipeline">{counts.rows.map((row:any,index:number)=><div className="pipeline-row" key={index}><b>{row.status||'n/a'}</b><span>{row.employer||row.company||'n/a'}</span><span>{row.title||row.role||'n/a'}</span></div>)}</div>}
      </>
      :tab==='due'?<>
        {counts.cadence&&<p className="kbd">{`${counts.cadence.total_tracked} tracked, ${counts.cadence.actionable} actionable, ${counts.cadence.undated} undated, ${counts.cadence.retired} retired`}</p>}
        {counts.cadence?.note&&<p className="sync-note">{counts.cadence.note}</p>}
        {counts.rows.length===0?<EmptyState title="Nothing is due">
          <p>Follow-up dates come from <code>job-history.md</code>; an undated application cannot be overdue.</p>
        </EmptyState>
          :<div className="table-wrap"><table className="data-table"><thead><tr><th scope="col">Status</th><th scope="col">Employer</th><th scope="col">Role</th><th scope="col">Last touch</th><th scope="col">Age</th></tr></thead>
            <tbody>{counts.rows.map((row:any,index:number)=><tr key={index}><td>{row.status||'n/a'}</td><td>{row.employer||row.company||'n/a'}</td><td>{row.title||row.role||'n/a'}</td><td>{row.applied_date||row.date||'n/a'}</td><td className={row.overdue?'stale':''}>{row.days??row.age_days??'n/a'}</td></tr>)}</tbody></table></div>}
      </>
      :tab==='ranked'?<>
        {!counts.present?<EmptyState title="No corpus to rank">
          <p>Capture a board first; the ranking reads the corpus those captures build.</p>
        </EmptyState>
          :<>
            <p className="kbd">{`${counts.rows} rows, ${counts.fits?Object.entries(counts.fits).map(([key,value])=>`${key} ${value}`).join(', '):''}`}</p>
            <div className="table-wrap"><table className="data-table"><thead><tr><th scope="col">Fit</th><th scope="col">Role</th><th scope="col">Employer</th><th scope="col">Source</th><th scope="col">Posting</th></tr></thead>
              <tbody>{(counts.top??[]).map((row:any,index:number)=><tr key={index}><td>{row.fit||'n/a'}</td><td>{row.title||'n/a'}</td><td>{row.employer||'n/a'}</td><td>{row.source||'n/a'}</td><td>{row.url?<a href={row.url} target="_blank" rel="noreferrer noopener">open</a>:(row.posting_status||'n/a')}</td></tr>)}</tbody></table></div>
            {counts.hash&&<p className="kbd">{`corpus hash ${counts.hash}`}</p>}
          </>}
      </>
      :<>
        <p className="sync-note">Read-only. Prohibited sources are refused by the runner.</p>
        <div className="table-wrap"><table className="data-table"><thead><tr><th scope="col">Source</th><th scope="col">Policy</th><th scope="col">Endpoint</th></tr></thead>
          <tbody>{Object.entries(counts.permitted??{}).map(([name,entry]:[string,any])=><tr key={name}><td>{name}</td><td>{entry.policy}</td><td>{entry.endpoint}</td></tr>)}</tbody></table></div>
        {counts.prohibited?.length>0&&<div className="notice">Refused by design: {counts.prohibited.join(', ')}.</div>}
      </>}
    </div>
  </div>;
}
