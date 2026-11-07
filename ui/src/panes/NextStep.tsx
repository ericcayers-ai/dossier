import type {ReactNode} from 'react';
import {agentApi} from '../lib/api';
import {useLoad} from '../lib/useLoad';

/** The engine's answer to the only question a stranger has: what now?
 *
 *  `agent status` returns one next unit, its reason, and the blockers standing in
 *  front of it. This strip is that answer, in one card, with one action: the
 *  label names the unit, the sentence says why, and the button opens the pane that
 *  fixes it. The counts it used to print are now the four-step list beside it, so
 *  a number appears once.
 *
 *  It renders nothing while loading and nothing on failure: the shell already says
 *  whether the API is reachable, and a second error line here would be noise. */
export default function NextStep({onGo}:{onGo:(pane:string)=>void}):ReactNode{
  const status=useLoad(()=>agentApi.status(),[]);
  if(status.state.status!=='ready')return null;
  const data=status.state.data;
  const unit=data.next;
  if(!unit)return null;
  const target=PANE_OF[unit.mode]??'agent';
  /* The reason and the first blocker usually say the same thing in two sentences
     ("No base .docx in this folder." twice). A blocker the reason already carries
     is not repeated; the rest sit behind a summary so the card stays one fact, one
     action, one line. */
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
  </div>;
}

const PANE_OF:Record<string,string>={
  setup:'files',identity:'identity',match:'jobs',capture:'capture',build:'build',
  verify:'verify',audit:'audit',sources:'audit',track:'jobs',apply:'jobs',panel:'panel',
  interview:'agent',upskill:'agent',negotiate:'agent',handback:'agent',
};
const LABEL_OF:Record<string,string>={'files':'Folder',identity:'Identity',jobs:'Jobs',
  capture:'Capture',build:'Build',verify:'Verify',audit:'Audit',agent:'Loop',panel:'Panel'};
