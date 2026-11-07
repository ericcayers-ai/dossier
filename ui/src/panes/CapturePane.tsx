import {useState} from 'react';
import type {ReactNode} from 'react';
import {api} from '../lib/api';
import type {ScrapeCapture,ScrapeRun,ScrapeStatus} from '../lib/api';
import {useLoad} from '../lib/useLoad';
import {ErrorState,Loading} from './StateViews';
import {count,isOne} from '../lib/copy';

/** Capture is the pane the engine's scraping had no surface for: pick a board,
 *  scrape one page, or walk a recipe, and read exactly what arrived. The engine
 *  decides `complete`; this pane never upgrades a partial run to a success. */
export default function CapturePane():ReactNode{
  const status=useLoad<ScrapeStatus>(()=>api.scrapeStatus(),[]);
  const [url,setUrl]=useState('');
  const [source,setSource]=useState('');
  const [session,setSession]=useState(false);
  const [challenge,setChallenge]=useState('');
  const [recipe,setRecipe]=useState('');
  const [limit,setLimit]=useState('10');
  const [busy,setBusy]=useState<'page'|'recipe'|null>(null);
  const [capture,setCapture]=useState<ScrapeCapture|null>(null);
  const [run,setRun]=useState<ScrapeRun|null>(null);
  const [error,setError]=useState<unknown>(null);

  const recipes=status.state.status==='ready'?status.state.data.recipes:[];
  const chosen=recipes.find(item=>item.id===recipe);

  const scrapePage=async()=>{
    setBusy('page');setError(null);setCapture(null);
    try{
      const result=await api.scrapeCapture({url:url.trim(),source:source.trim()||undefined,session,challenge:challenge||undefined,refresh:true});
      setCapture(result);
    }catch(reason){setError(reason)}finally{setBusy(null)}
  };

  const runRecipe=async()=>{
    if(!chosen)return;
    setBusy('recipe');setError(null);setRun(null);
    try{
      const result=await api.scrapeRun({recipe:chosen.id,limit:Number.parseInt(limit,10)||10,challenge:challenge||undefined});
      setRun(result);
      status.reload();
    }catch(reason){setError(reason)}finally{setBusy(null)}
  };

  return <div className="audit-pane">
    <div className="audit-head">
      <div>
        <h1>Capture</h1>
      </div>
    </div>

    {status.state.status==='loading'?<Loading what="capture status"/>
      :status.state.status==='failed'?<ErrorState error={status.state.error} what="Reading capture status" onRetry={status.reload}/>
      :<>
        <div className="chips" role="status" aria-live="polite">
          {Object.entries(status.state.data.engines).map(([name,engine])=><span className={`chip static ${engine.available?'active':''}`} key={name}>{name}{engine.available?` ${engine.version??''}`:' missing'}</span>)}
          <span className="chip static">{`challenge: ${status.state.data.challenge.configured}`}</span>
          <span className="chip static">{`${count(status.state.data.captured_postings,'posting')} archived`}</span>
        </div>
        {!status.state.data.engines.playwright?.available&&<p className="notice">No Playwright, so an authenticated capture is unavailable. Install it with <code>uv sync --all-extras</code>.</p>}

        <h2 className="pane-title">One page</h2>
        <div className="field-row">
          <label className="field"><span>Page URL</span><input value={url} onChange={event=>setUrl(event.target.value)} placeholder="https://boards.example/job/123"/></label>
          <label className="field"><span>Source</span><input value={source} onChange={event=>setSource(event.target.value)} placeholder="blank = resolve from the host"/></label>
          <label className="field"><span>Challenge</span><select value={challenge} onChange={event=>setChallenge(event.target.value)}>
            <option value="">workspace policy ({status.state.data.challenge.configured})</option>
            {status.state.data.challenge.policies.map(policy=><option key={policy} value={policy}>{policy}</option>)}
          </select></label>
          <label className="chip"><input type="checkbox" checked={session} onChange={event=>setSession(event.target.checked)}/> use saved session</label>
        </div>
        <div className="button-row">
          <button type="button" className="primary" onClick={()=>void scrapePage()} disabled={busy!==null||!url.trim()}>{busy==='page'?'Scraping…':'Scrape page'}</button>
        </div>

        <h2 className="pane-title">A whole board</h2>
        <p className="sync-note">Recipes live in <code>.dossier/scrapes/</code>.</p>
        <div className="field-row">
          <label className="field"><span>Recipe</span><select value={recipe} onChange={event=>setRecipe(event.target.value)}>
            <option value="">choose a recipe…</option>
            {recipes.map(item=><option key={item.id} value={item.id}>{`${item.id} (${item.source}, ${item.kind}${item.due?', due':''})`}</option>)}
          </select></label>
          <label className="field"><span>Item limit</span><input value={limit} onChange={event=>setLimit(event.target.value)} inputMode="numeric"/></label>
        </div>
        {chosen&&<p className="sync-note">{`${chosen.start_url}${chosen.last_run?.captured_at?`, last run ${chosen.last_run.captured_at} (${chosen.last_run.complete?'complete':'partial'})`:''}`}</p>}
        <div className="button-row">
          <button type="button" onClick={()=>void runRecipe()} disabled={busy!==null||!chosen}>{busy==='recipe'?'Walking the board…':'Run recipe'}</button>
          <button type="button" onClick={()=>status.reload()}>Refresh status</button>
        </div>

        {error?<ErrorState error={error} what="Running the capture"/>:null}

        {capture&&<section className="results" aria-label="Capture result">
          <div className="result-line">
            <b>{capture.complete?'Complete':'Partial'}</b>
            <span className={capture.complete?'verdict pass':'verdict fail'}>{capture.driver??'n/a'}</span>
            <span>{capture.posting??capture.reason??''}</span>
          </div>
          {capture.title&&<p className="sync-note">{capture.title}</p>}
          {capture.challenge&&Boolean((capture.challenge as Record<string,unknown>).detected)&&<p className="notice">{`Challenge: ${String((capture.challenge as Record<string,unknown>).detected)}. Policy ${String((capture.challenge as Record<string,unknown>).policy??'n/a')}, resolved by ${String((capture.challenge as Record<string,unknown>).resolved_by??'n/a')}.`}</p>}
          {capture.reason&&!capture.complete&&<p className="notice">{capture.reason}</p>}
        </section>}

        {run&&<section className="results" aria-label="Recipe result">
          <div className="result-line">
            <b>{run.complete?'Complete':'Partial'}</b>
            <span className={run.complete?'verdict pass':'verdict fail'}>{`${run.items_captured}/${run.items}`}</span>
            <span>{run.reason??`${run.duplicates.length} duplicate, ${run.failures.length} failed`}</span>
          </div>
          {run.written.length>0&&<div className="table-wrap"><table className="data-table"><thead><tr><th scope="col">Role</th><th scope="col">Employer</th><th scope="col">Posting</th></tr></thead>
            <tbody>{run.written.map(row=><tr key={row.url}><td>{row.title||'n/a'}</td><td>{row.company||'n/a'}</td><td>{row.path||'n/a'}</td></tr>)}</tbody></table></div>}
          {run.duplicates.length>0&&<p className="sync-note">{`${run.duplicates.length} already archived (pass refresh to re-capture).`}</p>}
          {run.failures.map(failure=><p className="notice" key={`${failure.stage}-${failure.url}`}>{`${failure.stage}: ${failure.url}. ${failure.error}`}</p>)}
        </section>}
      </>}
  </div>;
}
