import {useState} from 'react';
import type {ReactNode} from 'react';
import {ApiError,api} from '../lib/api';
import type {TemplateFill,TemplateVerify} from '../lib/api';
import {ErrorState} from './StateViews';
import {count,isOne} from '../lib/copy';

/** "Provide template": the user's own .docx, filled in place.
 *
 *  The point of the pane is that the layout is never rebuilt — the output is the
 *  user's file with `{{placeholders}}` replaced. So the pane does exactly two
 *  things: read the placeholders the template declares, then fill them. A
 *  leftover placeholder is refused with the list, not shipped as a document. */
export default function BuildPane({docx=[]}:{docx?:string[]}):ReactNode{
  const [template,setTemplate]=useState('');
  const [out,setOut]=useState('resume-from-template.docx');
  const [declared,setDeclared]=useState<string[]|null>(null);
  const [values,setValues]=useState<Record<string,string>>({});
  const [busy,setBusy]=useState<'read'|'fill'|'verify'|null>(null);
  const [report,setReport]=useState<TemplateFill|null>(null);
  const [verdict,setVerdict]=useState<TemplateVerify|null>(null);
  const [leftovers,setLeftovers]=useState<string[]>([]);
  const [error,setError]=useState<unknown>(null);

  const readFields=async()=>{
    setBusy('read');setError(null);setLeftovers([]);setVerdict(null);setReport(null);
    try{
      const result=await api.templateFields(template.trim());
      setDeclared(result.fields);
      setValues(current=>{
        const next={...current};
        result.fields.forEach(field=>{if(!(field in next))next[field]=''});
        return next;
      });
    }catch(reason){setDeclared(null);setError(reason)}finally{setBusy(null)}
  };

  const fill=async()=>{
    setBusy('fill');setError(null);setLeftovers([]);setVerdict(null);
    try{
      const spec={fields:Object.fromEntries(Object.entries(values).map(([key,value])=>[key,value]))};
      const result=await api.fillTemplate({template:template.trim(),out:out.trim(),spec});
      setReport(result);
    }catch(reason){
      setReport(null);
      // A 422 is the leftover gate: the document was refused on purpose and the
      // response carries the placeholder list, which is the useful part.
      if(reason instanceof ApiError&&reason.status===422){
        try{
          const detail=JSON.parse(reason.detail) as {detail?:{leftovers?:string[]};leftovers?:string[]};
          const list=detail.leftovers??detail.detail?.leftovers??[];
          setLeftovers(list);
        }catch{/* not structured; the message still renders */}
      }
      setError(reason);
    }finally{setBusy(null)}
  };

  const verify=async()=>{
    if(!report)return;
    setBusy('verify');setError(null);
    try{
      const spec={fields:Object.fromEntries(Object.entries(values))};
      // The paths the user typed, not the absolute ones the API echoes back: the API
      // rejects an absolute path by design (`resolve_in_root`), and `report` carries
      // the resolved form.
      setVerdict(await api.verifyTemplateInline({template:template.trim(),candidate:out.trim(),spec}));
    }catch(reason){setError(reason)}finally{setBusy(null)}
  };

  const filled=Object.values(values).filter(value=>value.trim()).length;
  const missing=declared?declared.filter(field=>!(values[field]??'').trim()):[];

  return <div className="audit-pane">
    <div className="audit-head">
      <div>
        <h1>Build</h1>
      </div>
    </div>

    {/* The pane used to offer a template path it had invented, while the folder held
        three .docx files and the engine reported "no base .docx" elsewhere. It now
        lists what is actually here. */}
    {docx.length>0
      ? <p className="sync-note">{`${count(docx.length,'.docx file')} in this folder — start typing to pick one.`}</p>
      : <p className="notice">This folder has no <code>.docx</code>, so there is nothing to clone. Add the resume you want the layout copied from, then reload.</p>}
    <div className="field-row">
      <label className="field"><span>Template (.docx, relative to the workspace)</span>
        <input value={template} onChange={event=>setTemplate(event.target.value)} placeholder="templates/my-resume-template.docx" list="build-docx"/>
        <datalist id="build-docx">{docx.map(rel=><option key={rel} value={rel}/>)}</datalist>
      </label>
      <label className="field"><span>Output (.docx)</span><input value={out} onChange={event=>setOut(event.target.value)} placeholder="resume-from-template.docx"/></label>
    </div>
    <div className="button-row">
      <button type="button" className="primary" onClick={()=>void readFields()} disabled={busy!==null||!template.trim()}>{busy==='read'?'Reading…':'Read placeholders'}</button>
      <button type="button" onClick={()=>void fill()} disabled={busy!==null||!template.trim()||!out.trim()||!declared||filled===0}>{busy==='fill'?'Filling…':'Build from template'}</button>
      {report&&<button type="button" onClick={()=>void verify()} disabled={busy!==null}>{busy==='verify'?'Checking…':'Check the document'}</button>}
    </div>

    {declared&&declared.length===0&&<p className="notice">That template has no <code>{'{{placeholders}}'}</code>. Add tokens like <code>{'{{Name}}'}</code>, save, and read the fields again.</p>}

    {declared&&declared.length>0&&<section aria-label="Template fields">
      <p className="sync-note">{`${count(declared.length,'placeholder')}, ${filled} filled`}{missing.length?`, still empty: ${missing.join(', ')}`:''}</p>
      <div className="field-row">
        {declared.map(field=><label className="field" key={field}>
          <span>{field}</span>
          <input value={values[field]??''} onChange={event=>setValues(current=>({...current,[field]:event.target.value}))} placeholder={`value for {{${field}}}`}/>
        </label>)}
      </div>
    </section>}

    {leftovers.length>0&&<div className="notice">{`Refused: ${count(leftovers.length,'placeholder')} would stay in the document: ${leftovers.join(', ')}.`}</div>}
    {error?<ErrorState error={error} what="Filling the template"/>:null}

    {report&&<section className="results" aria-label="Template fill report">
      <div className="result-line">
        <b>{report.written?'Written':'Not written'}</b>
        <span className="verdict pass">{`${Object.values(report.replaced).reduce((total,value)=>total+value,0)} filled`}</span>
        <span>{report.output}</span>
      </div>
      {report.unused.length>0&&<p className="sync-note">{`Unused: ${report.unused.join(', ')}`}</p>}
      {report.leftovers.length>0&&<p className="notice">{`Unfilled: ${report.leftovers.join(', ')}`}</p>}
      {verdict&&<>
        <p className="verdict" role="status">{verdict.passed?'Every template check passed.':'A template check failed.'}</p>
        {verdict.checks.map(check=><div className="result-line" key={check.id}><b>{check.id}</b><span className={check.ok?'verdict pass':'verdict fail'}>{check.ok?'pass':'fail'}</span><span>{check.detail}</span></div>)}
      </>}
    </section>}
  </div>;
}
