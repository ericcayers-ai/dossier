import {useEffect,useState} from 'react';
import type {ReactNode} from 'react';
import {agentApi,fault} from '../lib/api';
import type {AgentContract,AgentStatus,CommitResult,WorkspaceState} from '../lib/api';
import {useLoad} from '../lib/useLoad';
import {ErrorState,Loading} from './StateViews';
import {count} from '../lib/copy';

const HANDBACK_TEMPLATE=JSON.stringify({mode:'build',status:'partial',artifacts:[{path:'relative/path.docx'}],evidence:['verbatim output line'],gaps:['what is still missing'],next:[]},null,2);

function CommitForm({onCommitted}:{onCommitted:()=>void}):ReactNode{
  const [text,setText]=useState(HANDBACK_TEMPLATE);
  const [result,setResult]=useState<CommitResult|null>(null);
  const [error,setError]=useState('');
  const [busy,setBusy]=useState(false);

  const submit=async()=>{
    let payload:Record<string,unknown>;
    try{payload=JSON.parse(text) as Record<string,unknown>}
    catch(reason){setError(`That is not valid JSON: ${reason instanceof Error?reason.message:'unparsable'}`);setResult(null);return}
    setBusy(true);setError('');
    try{
      const outcome=await agentApi.commit(payload);
      setResult(outcome);
      if(outcome.accepted)onCommitted();
    }catch(reason){
      const {title,next}=fault(reason,'Committing the handback');
      setError(`${title} ${next}`);
      setResult(null);
    }finally{setBusy(false)}
  };

  return <div className="agent-commit">
    <h2>Commit a handback</h2>
    <label className="field"><span>Handback JSON</span>
      <textarea value={text} onChange={event=>setText(event.target.value)} spellCheck={false}/>
    </label>
    <div className="button-row">
      <button type="button" className="primary" onClick={()=>void submit()} disabled={busy}>{busy?'Committing…':'Commit handback'}</button>
      <button type="button" onClick={()=>{setText(HANDBACK_TEMPLATE);setResult(null);setError('')}}>Reset template</button>
      {result&&<span className={result.accepted?'accepted':'rejected'}>{result.accepted?`Accepted. Session ${result.sessions} recorded.`:'Rejected.'}</span>}
    </div>
    {error&&<div className="notice" role="alert">{error}</div>}
    {result&&!result.accepted&&<pre role="alert">{`${(result.problems??['no reason given']).join('\n')}${result.expected?`\n\nexpected fields: ${result.expected.join(', ')}`:''}`}</pre>}
    {result?.accepted&&result.next&&<p className="reason">{`Next: ${result.next.label}.`}</p>}
  </div>;
}

export default function AgentPane():ReactNode{
  const contract=useLoad<AgentContract>(()=>agentApi.contract(),[]);
  const meta=useLoad<{status:AgentStatus;workspace:WorkspaceState;doctor:{verdict:string;capabilities:Record<string,boolean>;blockers:string[];platform:Record<string,string>}}>(async()=>({
    status:await agentApi.status(),
    workspace:await agentApi.workspace(),
    doctor:await agentApi.doctor(),
  }),[]);
  const prompt=useLoad(()=>agentApi.prompt(),[]);
  const adapters=useLoad(()=>agentApi.adapters(),[]);

  const [mode,setMode]=useState('build');
  /* `setMode(mode)` is a React no-op (same value, no re-render), so the Refresh
     chip bumped this counter instead — the packet now actually re-renders. */
  const [briefTicket,setBriefTicket]=useState(0);
  const [brief,setBrief]=useState('');
  const [briefError,setBriefError]=useState('');
  const [busy,setBusy]=useState(false);
  const [copied,setCopied]=useState('');

  const unit=meta.state.status==='ready'?meta.state.data.status.next:null;
  useEffect(()=>{if(unit?.mode)setMode(unit.mode)},[unit?.mode]);
  useEffect(()=>{
    let live=true;
    setBusy(true);
    agentApi.brief(mode).then(text=>{if(live){setBrief(text);setBriefError('')}})
      .catch(reason=>{if(live){setBrief('');const {title,next}=fault(reason,'Rendering the task packet');setBriefError(`${title} ${next}`)}})
      .finally(()=>{if(live)setBusy(false)});
    return()=>{live=false};
  },[mode,briefTicket]);

  const copy=async(what:string,text:string)=>{
    if(!text)return;
    try{await navigator.clipboard.writeText(text);setCopied(what);window.setTimeout(()=>setCopied(''),1500)}catch{setCopied('')}
  };

  if(contract.state.status==='loading')return <div className="pane-scroll"><Loading what="the agent contract"/></div>;
  if(contract.state.status==='failed')return <ErrorState error={contract.state.error} what="Reading the agent contract" onRetry={contract.reload}/>;
  const data=contract.state.data;

  return <div className="agent-pane">
    <div className="agent-head">
      <div>
        <h1>Loop</h1>
      </div>
      <span className="grow"/>
      <span className="agent-version">{`${data.modes.length} modes`}</span>
      <span className="agent-version">{`${data.gates.length} gates`}</span>
    </div>

    {unit&&<div className={`agent-next ${unit.needs_user?'needs-user':''}`}>
      <div className="row"><span className="mode">{unit.label}</span><span className={`agent-kind ${unit.kind}`}>{unit.kind}</span><span className="agent-version">{unit.stage}</span>{unit.needs_user&&<span className="agent-version">needs the user</span>}</div>
      <p className="reason">{unit.reason}</p>
      {unit.targets&&unit.targets.length>0&&<ul>{unit.targets.slice(0,6).map(target=><li key={target}>{target}</li>)}</ul>}
    </div>}

    <div className="agent-columns">
      <div className="agent-modes">
        <h2>Modes</h2>
        <ul>{data.modes.map(item=><li key={item.id}><button type="button" aria-current={item.id===mode} onClick={()=>setMode(item.id)}><span>{item.label}</span><span className={`agent-kind ${item.kind}`}>{item.kind}</span></button></li>)}</ul>
      </div>

      <div>
        <div className="agent-brief">
          <div className="bar"><b>{`Task packet for ${mode}`}</b><span className="grow"/>{busy&&<span className="agent-version">rendering…</span>}<button type="button" className="chip" onClick={()=>setBriefTicket(value=>value+1)}>Refresh</button><button type="button" className="primary" onClick={()=>void copy('packet',brief)} disabled={!brief}>{copied==='packet'?'Copied':'Copy packet'}</button></div>
          {/* The packet is forty lines of instructions for another agent. The screen
              offers the two things a person does here — read it or copy it — and keeps
              the text one click away instead of filling the pane with a wall. */}
          <details className="agent-packet">
            <summary>{briefError?'The packet could not be rendered':'Show the brief'}</summary>
            <pre role="region" tabIndex={0} aria-label="Agent task packet">{briefError||brief||'No packet rendered.'}</pre>
          </details>
        </div>

        <CommitForm onCommitted={meta.reload}/>

        <div className="agent-gates">
          <h2>Gates</h2>
          <p className="gate-lede">{`${data.gates.length} rules, each enforced in code.`}</p>
          {data.gates.map(gate=><details className="gate" key={gate.id}>
            <summary><b>{gate.id}</b></summary>
            <p>{gate.rule}</p>
            <p className="gate-never"><span>Never</span> {gate.never}</p>
            <p className="gate-by"><code>{gate.enforced_by}</code></p>
          </details>)}
        </div>

        <div className="agent-facts">
          <h2>Workspace</h2>
          {meta.state.status==='loading'?<Loading what="the workspace state"/>
            :meta.state.status==='failed'?<ErrorState inline error={meta.state.error} what="Reading the workspace state" onRetry={meta.reload}/>
            :<>
              <dl>
                <dt>Root</dt><dd>{meta.state.data.workspace.root||meta.state.data.status.root||'n/a'}</dd>
                <dt>Files</dt><dd>{meta.state.data.workspace.counts?.files??'n/a'}</dd>
                <dt>Postings</dt><dd>{meta.state.data.workspace.counts?.postings??'n/a'}</dd>
                <dt>Generated resumes</dt><dd>{meta.state.data.workspace.counts?.artefacts??'n/a'}</dd>
                <dt>Corpus</dt><dd>{meta.state.data.workspace.corpus?.present?`${meta.state.data.workspace.corpus.rows} rows across ${meta.state.data.workspace.corpus.sources_count} boards, fits ${JSON.stringify(meta.state.data.workspace.corpus.fits)}`:'n/a'}</dd>
                <dt>Tracker</dt><dd>{meta.state.data.workspace.tracker?.present?`${meta.state.data.workspace.tracker.rows} rows, ${JSON.stringify(meta.state.data.workspace.tracker.status_counts)}`:'n/a'}</dd>
                <dt>Coverage</dt><dd>{meta.state.data.workspace.coverage?.present?`${meta.state.data.workspace.coverage.file} (${count(meta.state.data.workspace.coverage.age_days,'day')} old)`:'n/a'}</dd>
                <dt>Capabilities</dt><dd>{`${meta.state.data.doctor.verdict}. ${Object.entries(meta.state.data.doctor.capabilities).filter(([,ok])=>ok).length}/${Object.keys(meta.state.data.doctor.capabilities).length} available`}</dd>
              </dl>
              {meta.state.data.workspace.blockers.length>0&&<ul className="agent-blockers">{meta.state.data.workspace.blockers.map(blocker=><li key={blocker}>{blocker}</li>)}</ul>}
              {meta.state.data.status.recent.length>0&&<ul className="agent-sessions">{meta.state.data.status.recent.map((entry,index)=><li key={index}><b>{entry.mode}</b><span>{entry.status}</span><span>{entry.at}</span></li>)}</ul>}
            </>}
        </div>

        <details className="agent-prompt">
          <summary><h2>System prompt</h2></summary>
          {prompt.state.status==='loading'?<Loading what="the system prompt"/>
            :prompt.state.status==='failed'?<ErrorState inline error={prompt.state.error} what="Reading the system prompt" onRetry={prompt.reload}/>
            :<>
              <div className="button-row"><button type="button" onClick={()=>void copy('prompt',prompt.state.status==='ready'?prompt.state.data:'')}>{copied==='prompt'?'Copied':'Copy system prompt'}</button></div>
              <pre>{prompt.state.data}</pre>
            </>}
        </details>

        <div className="agent-facts">
          <h2>Adapter packs</h2>
          {adapters.state.status==='loading'?<Loading what="the adapter packs"/>
            :adapters.state.status==='failed'?<ErrorState inline error={adapters.state.error} what="Reading the adapter packs" onRetry={adapters.reload}/>
            :(()=>{
              const packs=adapters.state.data.packs;
              const current=adapters.state.data.current;
              return <>
                <p className="reason">{`${packs.filter(pack=>current[pack]).length}/${packs.length} packs current.`}</p>
                <div className="agent-packs">{packs.map(pack=><div key={pack} className={current[pack]?'ok':'drift'}>{`${current[pack]?'current':'drifted'}: ${pack}`}</div>)}</div>
              </>;
            })()}
        </div>
      </div>
    </div>
  </div>;
}
