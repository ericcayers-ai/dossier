import type {ReactNode} from 'react';
import {api} from '../lib/api';
import {useLoad} from '../lib/useLoad';
import {ErrorState,Loading} from './StateViews';

export default function AuditPane():ReactNode{
  const audit=useLoad(()=>api.audit(),[]);
  const sources=useLoad(()=>api.sources(),[]);

  // The heading stays while the body loads: a pane that changes identity when
  //  data lands loses the reader's place (and shifts the layout under them).
  if(audit.state.status==='loading')return <div className="audit-pane">
    <div className="audit-head"><div><h1>Audit</h1></div></div>
    <Loading what="the workspace audit" rows={5}/>
  </div>;
  if(audit.state.status==='failed')return <div className="audit-pane">
    <div className="audit-head"><div><h1>Audit</h1></div></div>
    <ErrorState error={audit.state.error} what="Reading the workspace audit" onRetry={audit.reload}/>
  </div>;
  const data=audit.state.data;

  return <div className="audit-pane">
    <div className="audit-head">
      <div>
        <h1>Audit</h1>
        <p className="pane-purpose">A health check of the folder: what is missing, what is out of date, and which job boards Dossier may read.</p>
      </div>
      <span className="audit-date">Generated {data.generated_on}</span>
    </div>

    <div className="audit-counts" role="list">
      {Object.entries(data.counts).map(([key,value])=><div className="audit-count" role="listitem" key={key}><b>{value}</b><span>{key.replaceAll('_',' ')}</span></div>)}
    </div>

    <h2>Checks</h2>
    <div>
      {data.checks.length===0&&<p className="empty">No checks ran.</p>}
      {data.checks.map(check=><div className={`audit-check ${check.status}`} key={check.id}><span className="audit-status">{check.status}</span><div><b>{check.label}</b><p>{check.detail}</p></div></div>)}
    </div>

    <h2>Source policy ledger</h2>
    {sources.state.status==='loading'?<Loading what="the source ledger"/>
      :sources.state.status==='failed'?<ErrorState inline error={sources.state.error} what="Reading the source ledger" onRetry={sources.reload}/>
      :(()=>{
        const table=(sources.state.data?.table??{}) as Record<string,Record<string,unknown>>;
        const names=Object.keys(table);
        if(names.length===0)return <p className="empty">No sources are registered for this folder. Add them to <code>.dossier/sources.json</code>.</p>;
        return <div>{names.map(name=>{
          const entry=table[name];
          const status=String(entry.status??'unknown');
          return <div className="source-row" key={name}>
            <b>{name}</b>
            <span className={`source-status ${status}`}>{status}</span>
            <span>{String(entry.detail??entry.capture_status??'')}</span>
            {Boolean(entry.manual_request)&&<small>Manual step required</small>}
          </div>;
        })}</div>;
      })()}

    <h2>Freshness flags</h2>
    {data.stale.length===0?<p className="empty">Nothing is stale.</p>:<ul className="agent-blockers">{data.stale.map(entry=><li key={entry}>{entry}</li>)}</ul>}

    <p className="sync-note">Read-only. It never changes a file.</p>
  </div>;
}
