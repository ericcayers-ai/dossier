import type {ReactNode} from 'react';
import {agentApi} from '../lib/api';
import {useLoad} from '../lib/useLoad';
import {count,isOne} from '../lib/copy';

/** The landing pane answers the only question a stranger has: what now?
 *
 *  The engine already knows — `agent status` returns one next unit, its reason, and
 *  the blockers standing in front of it — but before this strip that answer was two
 *  clicks deep under an area called "Agent". A workspace blocked on "no base .docx"
 *  therefore looked like an empty file browser.
 *
 *  It renders nothing while loading and nothing on failure: the shell already says
 *  whether the API is reachable, and a second error line on the welcome screen would
 *  be noise, not information. */
export default function NextStep({onGo}:{onGo:(pane:string)=>void}):ReactNode{
  const status=useLoad(()=>agentApi.status(),[]);
  if(status.state.status!=='ready')return null;
  const data=status.state.data;
  const unit=data.next;
  if(!unit)return null;
  const target=PANE_OF[unit.mode]??'agent';
  const counts=Object.entries(data.counts||{}).filter(([,value])=>Number(value)>0);
  /* The reason and the first blocker usually say the same thing in two sentences
     ("No base .docx in this folder." twice). A blocker the reason already carries
     is not repeated; the rest sit behind a summary so the welcome screen stays one
     fact, one action, one line. */
  const reason=(unit.reason||unit.summary||'').trim().toLowerCase();
  const fresh=(data.blockers||[]).filter(blocker=>!reason.includes(blocker.slice(0,48).toLowerCase()));
  const blockerList=<ul className="agent-blockers">{fresh.map(blocker=><li key={blocker}>{blocker}</li>)}</ul>;
  return <div className={`agent-next welcome-next ${unit.needs_user?'needs-user':''}`}>
    <div className="row">
      <span className="mode">{unit.needs_user?'Waiting on you':'Next'}: {unit.label}</span>
      <span className="grow"/>
      <button type="button" className="primary" onClick={()=>onGo(target)}>Open {LABEL_OF[target]??'the pane'}</button>
    </div>
    <p className="reason">{unit.reason||unit.summary}</p>
    {data.blockers.length>0&&fresh.length>0&&(fresh.length<=2?blockerList
      :<details className="agent-blockers-more">
        <summary>{`${fresh.length} blockers`}</summary>
        {blockerList}
      </details>)}
    {/* The same numbers as a stat row. A comma list of six counts left the pane hollow;
        one cell per count is the readout a light table should have. */}
    {counts.length>0&&<dl className="welcome-facts">
      {counts.map(([name,value])=><div className="welcome-fact" key={name}>
        <dt>{name.replace(/_/g,' ')}</dt><dd>{value}</dd>
      </div>)}
      {data.sessions>0&&<div className="welcome-fact"><dt>recorded sessions</dt><dd>{data.sessions}</dd></div>}
    </dl>}
  </div>;
}

const PANE_OF:Record<string,string>={
  setup:'files',identity:'identity',match:'jobs',capture:'capture',build:'build',
  verify:'verify',audit:'audit',sources:'audit',track:'jobs',apply:'jobs',panel:'panel',
  interview:'agent',upskill:'agent',negotiate:'agent',handback:'agent',
};
const LABEL_OF:Record<string,string>={'files':'Folder',identity:'Identity',jobs:'Jobs',
  capture:'Capture',build:'Build',verify:'Verify',audit:'Audit',agent:'Loop',panel:'Panel'};
