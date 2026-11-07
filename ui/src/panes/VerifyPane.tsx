import {useEffect,useState} from 'react';
import type {ReactNode} from 'react';
import {api,fault} from '../lib/api';
import type {VerifyReport} from '../lib/api';
import {ErrorState} from './StateViews';

/** The verify gate had no UI at all. It is the gate whose exit code the workflow
 *  asserts on, so it is the first capability wired (FINDINGS-INDEX B7 order). */
export default function VerifyPane({candidate='',files=[]}:{candidate?:string;files?:string[]}):ReactNode{
  const [base,setBase]=useState('');
  const [target,setTarget]=useState(candidate);
  const [pdf,setPdf]=useState('');
  const [pages,setPages]=useState('');
  const [busy,setBusy]=useState(false);
  const [report,setReport]=useState<VerifyReport|null>(null);
  const [error,setError]=useState<unknown>(null);

  useEffect(()=>{if(candidate)setTarget(candidate)},[candidate]);

  const run=async()=>{
    setBusy(true);
    setError(null);
    try{
      const result=await api.verify({base:base.trim(),candidate:target.trim(),pdf:pdf.trim(),expected_pages:Number.parseInt(pages,10)||0});
      setReport(result);
    }catch(reason){
      setReport(null);
      setError(reason);
    }finally{setBusy(false)}
  };

  const canRun=Boolean(base.trim()||target.trim()||pdf.trim());

  return <div className="verify-pane">
    <div className="audit-head">
      <div>
        <h1>Verify</h1>
        <p className="pane-purpose">Check a document before you send it: layout kept, text readable, pages rendered.</p>
      </div>
    </div>

    <div className="field-row">
      <label className="field"><span>Base document (source)</span><input value={base} onChange={event=>setBase(event.target.value)} placeholder="job-posting-….md" list="verify-base"/>
        <datalist id="verify-base">{files.slice(0,200).map(rel=><option key={rel} value={rel}/>)}</datalist></label>
      <label className="field"><span>Candidate document (tailored)</span><input value={target} onChange={event=>setTarget(event.target.value)} placeholder="….docx" list="verify-candidate"/>
        <datalist id="verify-candidate">{files.slice(0,200).map(rel=><option key={rel} value={rel}/>)}</datalist></label>
      <label className="field"><span>Rendered PDF</span><input value={pdf} onChange={event=>setPdf(event.target.value)} placeholder="….pdf" list="verify-pdf"/>
        <datalist id="verify-pdf">{files.slice(0,200).map(rel=><option key={rel} value={rel}/>)}</datalist></label>
      <label className="field"><span>Expected pages</span><input value={pages} onChange={event=>setPages(event.target.value)} inputMode="numeric" placeholder="1"/></label>
    </div>

    <div className="button-row">
      <button type="button" className="primary" onClick={()=>void run()} disabled={busy||!canRun}>{busy?'Verifying…':'Run verify'}</button>
      {report&&<button type="button" onClick={()=>{setReport(null);setError(null)}}>Clear result</button>}
    </div>

    {error?<ErrorState inline error={error} what="Running the verify gate"/>
      :report&&<>
        <p className="verdict" role="status">{report.passed?'Every check that ran passed.':report.checks.length===0?'No check could run with those inputs.':'A check failed.'}</p>
        {report.not_visually_verified&&<p className="notice">Not visually verified: no PDF was given, so the rendered-page check could not run.</p>}
        <div className="results">
          {report.checks.map(check=><div className="result-line" key={check.id}>
            <b>{check.id}</b>
            <span className={check.ok?'verdict pass':'verdict fail'}>{check.ok?'pass':'fail'}</span>
            <span>{check.detail}</span>
          </div>)}
          {report.skipped.map(entry=><div className="result-line" key={entry}><b>skipped</b><span className="verdict">skipped</span><span>{entry}</span></div>)}
        </div>
      </>}
    {!report&&!error&&<p className="sync-note">A PDF alone closes the text-layer and render checks. The source diff needs a base and a candidate.</p>}
  </div>;
}
