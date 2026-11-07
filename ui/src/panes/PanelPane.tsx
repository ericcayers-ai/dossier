import {useState} from 'react';
import type {ReactNode} from 'react';
import {api,fault} from '../lib/api';
import {ErrorState,Loading} from './StateViews';
import '../panel.css';

type Finding={reviewer:string;verdict:string;line:number|null;quote:string;why:string;fix:string;weight:number};
type Seat={id:string;name:string;asks:string;score:number;findings:Finding[]};
type Panel={score:number;verdict:string;lines:number;words:number;has_posting:boolean;
  seats:Seat[];plan:Array<{order:number;seat:string;line:number|null;quote:string;why:string;rewrite:string}>};

const BAND=(score:number)=>score>=80?'pass':score>=60?'warn':'fail';

/** Seven reviewers, one score each, and the line that cost the most.
 *
 *  The reel this comes from says the thing a rejection never tells you is *why*.
 *  So the pane leads with the number, then for each seat the exact quoted line and
 *  what to do about it, and ends with the chair's three rewrites. Nothing is
 *  generated prose: every quote is the document's own words. */
export default function PanelPane({candidate,files=[]}:{candidate:string;files?:string[]}):ReactNode{
  const [resume,setResume]=useState(candidate||'resume.md');
  const [posting,setPosting]=useState('');
  const [role,setRole]=useState('');
  const [result,setResult]=useState<Panel|null>(null);
  const [error,setError]=useState<unknown>(null);
  const [busy,setBusy]=useState(false);
  const [open,setOpen]=useState<string[]>([]);

  const run=async()=>{
    setBusy(true);setError(null);
    try{
      setResult(await api.panel(resume.trim(),posting.trim(),role.trim()));
    }catch(reason){
      setResult(null);
      const {title,next}=fault(reason,'Running the panel');
      setError({title,next});
    }finally{setBusy(false)}
  };

  const toggle=(id:string)=>setOpen(current=>current.includes(id)
    ?current.filter(item=>item!==id)
    :[...current,id]);

  return <div className="panel-pane">
    <div className="audit-head">
      <div>
        <h1>Panel</h1>
        <p>Seven reviewers score the resume against one posting and quote the line behind each
          objection. A rejection never tells you why; this does.</p>
      </div>
      <button type="button" className="primary" onClick={()=>void run()} disabled={busy||!resume.trim()}>
        {busy?'Reading…':'Run the panel'}
      </button>
    </div>

    <div className="field-row">
      <datalist id="panel-files">{files.map(rel=><option key={rel} value={rel}/>)}</datalist>
      <label className="field"><span>Resume (relative to the workspace)</span>
        <input value={resume} onChange={event=>setResume(event.target.value)} placeholder="resume.md" list="panel-files"/>
      </label>
      <label className="field"><span>Posting (optional, but three seats need it)</span>
        <input value={posting} onChange={event=>setPosting(event.target.value)} placeholder="posting.md" list="panel-files"/>
      </label>
      <label className="field"><span>Target role (if the posting does not name it)</span>
        <input value={role} onChange={event=>setRole(event.target.value)} placeholder="Support Engineer"/>
      </label>
    </div>

    {busy&&<Loading what="seven reviewers"/>}
    {error?<ErrorState error={error as never} what="Running the panel" onRetry={()=>void run()}/>:null}

    {result&&<>
      <div className={`panel-score ${BAND(result.score)}`}>
        <b>{result.score}</b>
        <span>{result.verdict}</span>
        <small>{`${result.lines} lines, ${result.words} words${result.has_posting?'':' — no posting supplied, two seats scored the resume alone'}`}</small>
      </div>

      <ul className="panel-seats">
        {result.seats.map(seat=><li key={seat.id} className={`panel-seat ${BAND(seat.score)}`}>
          <button type="button" className="panel-seat-head" aria-expanded={open.includes(seat.id)}
            onClick={()=>toggle(seat.id)}>
            <span className="panel-seat-name">{seat.name}</span>
            <span className="panel-seat-score">{seat.score}</span>
            <span className="panel-seat-asks">{seat.asks}</span>
          </button>
          {open.includes(seat.id)&&<div className="panel-seat-body">
            {seat.findings.length===0
              ?<p className="rail-empty">Nothing to raise.</p>
              :seat.findings.map((finding,index)=><div className="panel-finding" key={index}>
                <p><b>{finding.line?`Line ${finding.line}`:'Whole document'}</b> {finding.why}</p>
                {finding.quote&&<blockquote>{finding.quote}</blockquote>}
                <p className="reason">Fix: {finding.fix}</p>
              </div>)}
          </div>}
        </li>)}
      </ul>

      <section className="panel-plan">
        <h2>The chair&apos;s plan</h2>
        {result.plan.length===0
          ?<p className="reason">Nothing to rewrite: every seat passed.</p>
          :<ol>{result.plan.map(item=><li key={`${item.seat}-${item.order}`}>
            <b>{item.line?`Line ${item.line}`:'Whole document'}</b> ({item.seat}) {item.rewrite}
            {item.quote&&<blockquote>{item.quote}</blockquote>}
          </li>)}</ol>}
      </section>
    </>}
  </div>;
}
