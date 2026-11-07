import {useEffect,useMemo,useState} from 'react';
import type {ReactNode} from 'react';
import {api} from '../lib/api';
import type {IdentityQuestion,IdentityState,MatchReport} from '../lib/api';
import {useLoad} from '../lib/useLoad';
import {ErrorState,Loading} from './StateViews';
import {count,humanise,isOne} from '../lib/copy';

/** Identity is the target the whole search is aimed at.
 *
 *  Two ideas hold the pane together: the app asks only what it cannot derive
 *  (a questionnaire), and every value the documents supply is shown with the file
 *  and line it came from. Answers beat documents; a field with no source is not
 *  shown at all. The Matches tab then scores the corpus against exactly that. */

type Tab='profile'|'matches';

function asText(value:unknown):string{
  if(value===null||value===undefined)return '';
  if(Array.isArray(value))return value.join(', ');
  return String(value);
}

function Field({question,value,onChange}:{question:IdentityQuestion;value:string;onChange:(next:string)=>void}):ReactNode{
  const id=`identity-${question.id}`;
  if(question.kind==='choice'){
    return <label className="field" htmlFor={id}>
      <span>{question.prompt}{question.required?' *':''}</span>
      <select id={id} value={value} onChange={event=>onChange(event.target.value)}>
        <option value="">Choose one…</option>
        {question.choices.map(choice=><option key={choice} value={choice}>{choice}</option>)}
      </select>
      {question.help&&<small className="sync-note">{question.help}</small>}
    </label>;
  }
  if(question.kind==='number'){
    return <label className="field" htmlFor={id}>
      <span>{question.prompt}{question.required?' *':''}</span>
      <input id={id} inputMode="numeric" value={value} onChange={event=>onChange(event.target.value)} />
      {question.help&&<small className="sync-note">{question.help}</small>}
    </label>;
  }
  return <label className="field" htmlFor={id}>
    <span>{question.prompt}{question.required?' *':''}</span>
    <input id={id} value={value} onChange={event=>onChange(event.target.value)}
           placeholder={question.kind==='list'?'comma separated':''}/>
    {question.help&&<small className="sync-note">{question.help}</small>}
  </label>;
}

export default function IdentityPane():ReactNode{
  const loaded=useLoad<IdentityState>(()=>api.identity(),[]);
  const [tab,setTab]=useState<Tab>('profile');
  const [draft,setDraft]=useState<Record<string,string>>({});
  const [busy,setBusy]=useState<'save'|'write'|'match'|null>(null);
  const [notice,setNotice]=useState('');
  const [error,setError]=useState<unknown>(null);
  const [matches,setMatches]=useState<MatchReport|null>(null);
  const [minBand,setMinBand]=useState('');

  const state=loaded.state;
  useEffect(()=>{
    if(state.status!=='ready')return;
    const next:Record<string,string>={};
    state.data.question_list.forEach(question=>{next[question.id]=asText(question.value)});
    setDraft(next);
  },[state]);

  const questions=state.status==='ready'?state.data.question_list:[];
  const grouped=useMemo(()=>{
    const groups:Array<{name:string;questions:IdentityQuestion[]}>=[];
    questions.forEach(question=>{
      const group=groups.find(item=>item.name===question.group);
      if(group)group.questions.push(question);
      else groups.push({name:question.group,questions:[question]});
    });
    return groups;
  },[questions]);

  const answered=Object.values(draft).filter(value=>value.trim()).length;
  const missing=state.status==='ready'?state.data.missing_required.filter(id=>!(draft[id]??'').trim()):[];

  const save=async()=>{
    setBusy('save');setError(null);setNotice('');
    try{
      const result=await api.identityAnswers(draft);
      setNotice(`Saved ${count(result.saved.length,'answer')}.`);
      loaded.reload();
    }catch(reason){setError(reason)}finally{setBusy(null)}
  };

  const write=async()=>{
    setBusy('write');setError(null);setNotice('');
    try{
      const result=await api.identityWrite();
      setNotice(`Wrote ${count(result.fields,'field')} to ${result.path}.`);
      loaded.reload();
    }catch(reason){setError(reason)}finally{setBusy(null)}
  };

  const runMatch=async()=>{
    setBusy('match');setError(null);
    try{setMatches(await api.match(30,minBand))}
    catch(reason){setError(reason)}finally{setBusy(null)}
  };

  return <div className="audit-pane">
    <div className="audit-head">
      <div>
        <h1>Identity</h1>
      </div>
    </div>

    <div className="tabs-row" role="tablist" aria-label="Identity sections">
      <button type="button" role="tab" id="identity-tab-profile" aria-controls="identity-panel-profile"
        aria-selected={tab==='profile'} className={tab==='profile'?'active':''} onClick={()=>setTab('profile')}>Profile</button>
      <button type="button" role="tab" id="identity-tab-matches" aria-controls="identity-panel-matches"
        aria-selected={tab==='matches'} className={tab==='matches'?'active':''} onClick={()=>setTab('matches')}>Matches</button>
    </div>

    <div role="tabpanel" id={`identity-panel-${tab}`} aria-labelledby={`identity-tab-${tab}`} tabIndex={0}>
    {state.status==='loading'?<Loading what="the identity"/>
      :state.status==='failed'?<ErrorState error={state.error} what="Reading the identity" onRetry={loaded.reload}/>
      :tab==='profile'?<>
        <p className="kbd" role="status" aria-live="polite">{`${state.data.answered} of ${state.data.questions} answered, ${state.data.sources.document??0} mined${state.data.complete?'':`, missing ${state.data.missing_required.join(', ')||'none'}`}`}</p>
        {grouped.map(group=><section key={group.name} aria-label={group.name}>
          <h2 className="pane-title">{group.name}</h2>
          <div className="field-row">
            {group.questions.map(question=><Field key={question.id} question={question}
              value={draft[question.id]??''}
              onChange={next=>setDraft(current=>({...current,[question.id]:next}))}/>)}
          </div>
        </section>)}

        {state.data.proposals.length>0&&<section aria-label="Mined from your documents">
          <h2 className="pane-title">Mined from your documents</h2>
          <p className="sync-note">Proposals, not answers. A field you leave blank keeps its document value.</p>
          <div className="table-wrap"><table className="data-table">
            <thead><tr><th scope="col">Field</th><th scope="col">Value</th><th scope="col">Source</th><th scope="col">Line</th></tr></thead>
            <tbody>{state.data.proposals.map(item=><tr key={item.field}>
              <td>{humanise(item.field)}</td><td>{asText(item.value).slice(0,90)}</td>
              <td>{item.source.split(/[\\/]/).pop()}</td><td>{item.line??'n/a'}</td>
            </tr>)}</tbody></table></div>
        </section>}

        <div className="button-row">
          <button type="button" className="primary" onClick={()=>void save()} disabled={busy!==null||answered===0}>{busy==='save'?'Saving…':'Save answers'}</button>
          <button type="button" onClick={()=>void write()} disabled={busy!==null||!state.data.fields||Object.keys(state.data.fields).length===0}>{busy==='write'?'Writing…':'Write IDENTITY.md'}</button>
          <span className="sync-note">{missing.length?`Still blank: ${missing.join(', ')}`:'Every required answer is present.'}</span>
        </div>
      </>
      :<>
        <div className="field-row">
          <label className="field"><span>Show at least</span>
            <select value={minBand} onChange={event=>setMinBand(event.target.value)}>
              <option value="">every band</option>
              <option value="strong">strong</option>
              <option value="possible">possible</option>
            </select>
          </label>
        </div>
        <div className="button-row">
          <button type="button" className="primary" onClick={()=>void runMatch()} disabled={busy!==null}>{busy==='match'?'Scoring…':'Score the corpus'}</button>
        </div>
        {!state.data.complete&&<p className="notice">{`Missing ${state.data.missing_required.join(', ')}, so this ranking is approximate.`}</p>}
        {matches&&!matches.present&&<p className="empty">{matches.reason??'No corpus yet.'}</p>}
        {matches&&matches.present&&<>
          <p className="kbd">{`scored ${matches.scored} of ${count(matches.rows,'row')}: `}{Object.entries(matches.band_counts).map(([band,count])=>`${band} ${count}`).join(', ')}</p>
          <div className="table-wrap"><table className="data-table">
            <thead><tr><th scope="col">Band</th><th scope="col">Score</th><th scope="col">Role</th><th scope="col">Employer</th><th scope="col">Why</th></tr></thead>
            <tbody>{matches.matched.map((row,index)=><tr key={`${row.url??row.title??index}`}>
              <td>{row.band}</td><td>{row.score}</td><td>{row.title||'n/a'}</td><td>{row.employer||'n/a'}</td>
              <td>{row.reasons.slice(0,2).join('. ')}</td>
            </tr>)}</tbody></table></div>
          {matches.disqualified.length>0&&<>
            <h2 className="pane-title">Disqualified</h2>
            <p className="sync-note">Kept visible: a score must not hide a deal-breaker.</p>
            <div className="table-wrap"><table className="data-table">
              <thead><tr><th scope="col">Role</th><th scope="col">Score</th><th scope="col">Reason</th></tr></thead>
              <tbody>{matches.disqualified.map((row,index)=><tr key={`dq-${index}`}>
                <td>{row.title||'n/a'}</td><td>{row.score}</td><td>{row.disqualifiers.join('; ')}</td>
              </tr>)}</tbody></table></div>
          </>}
        </>}
      </>}

    </div>
    {notice&&<p className="notice" role="status">{notice}</p>}
    {error?<ErrorState error={error} what="Working with the identity"/>:null}
  </div>;
}
