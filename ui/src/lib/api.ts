export type FileNode={rel:string;name?:string;kind?:string;ext?:string;size?:number;mtime?:string;mtime_ns?:number;directory?:boolean;children?:FileNode[]};
export type FileStamp={mtime_ns:number;sha256:string;size:number};
export type Member={rel:string;role:string;size?:number;mtime_ns?:number;stale?:boolean};
export type Bundle={stem_key?:string;members?:Member[];stale?:string[]};
export type Action={id:string;label:string;applies_to:string[];confirm:boolean;writes:boolean};
export type Audit={generated_on:string;checks:Array<{id:string;label:string;status:string;detail:string}>;counts:Record<string,number>;status_counts:Record<string,number>;stale:string[];source_status:Record<string,{status:string;policy:string;manual_request:boolean;detail:string}>;manual_sources:string[]};
export type TrajectoryNodeType='experience'|'contact'|'touchpoint'|'meeting'|'opportunity'|'milestone';
export type TrajectoryState='planned'|'active'|'complete'|'cancelled';
export type TrajectoryNode={id:string;type:TrajectoryNodeType;title:string;state:TrajectoryState;date:string|null;details:string;data:Record<string,unknown>;artifacts:string[];actionable?:boolean;blocked_by?:string[]};
export type TrajectoryLink={parent_id:string;child_id:string};
export type TrajectoryGraph={version:number;nodes:TrajectoryNode[];links:TrajectoryLink[]};
export type TreeNodeInput={id?:string;type:TrajectoryNodeType;title:string;state?:TrajectoryState;date?:string|null;details?:string;data?:Record<string,unknown>;artifacts?:string[]};

export type VerifyCheck={id:string;ok:boolean;detail:string;result:Record<string,unknown>};
export type VerifyReport={checks:VerifyCheck[];skipped:string[];passed:boolean;not_visually_verified:boolean};
export type ExportResult={path:string};
export type SourceLedger={table?:Record<string,Record<string,unknown>>;prohibited?:string[];manual_only?:string[];[key:string]:unknown};
export type TrackSummary={path:string;rows:number;status_counts:Record<string,number>;actionable:number;terminal:number;draft_only:number;actionable_without_date:string[];note:string};
export type CadenceEntry={[key:string]:unknown};
export type CadenceReport={analysis_date:string;total_tracked:number;actionable:number;undated:number;retired:number;counts:Record<string,number>;entries:CadenceEntry[];needs_date:string[];cadence:Record<string,number>;note:string};
export type CorpusReport={present:boolean;rows:number;fits?:Record<string,number>;top?:Array<{id?:string;title?:string;employer?:string;fit?:string;posting_status?:string;url?:string;source?:string}>;hash?:string};
export type FeedCatalog={permitted:Record<string,{policy:string;endpoint:string}>;prohibited:string[]};
export type Health={ok:boolean;root:string;indexed:number};

/** The identity: an answer beats a document, and every document value carries the
 *  file and line it came from. A field with neither is absent, not guessed. */
export type IdentityEvidence={path:string;line?:number|null;text?:string};
export type IdentityField={value:string|number|string[];source:'answer'|'document';confidence?:string;answered_at?:string|null;evidence?:IdentityEvidence|null};
export type IdentityQuestion={id:string;group:string;prompt:string;kind:'text'|'list'|'choice'|'number'|'bool';help:string;choices:string[];required:boolean;answered:boolean;value?:unknown;source?:string|null;evidence?:IdentityEvidence|null};
export type IdentityMine={field:string;value:string|string[];source:string;line:number|null;evidence:string;confidence:string};
export type IdentityState={root:string;fields:Record<string,IdentityField>;missing_required:string[];questions:number;answered:number;complete:boolean;sources:Record<string,number>;rule:string;question_list:IdentityQuestion[];proposals:IdentityMine[]};
export type MatchRow={title?:string;employer?:string;location?:string;url?:string;source?:string;score:number;band:'strong'|'possible'|'unlikely';reasons:string[];disqualifiers:string[]};
export type MatchReport={present:boolean;rows:number;scored:number;band_counts:Record<string,number>;matched:MatchRow[];disqualified:MatchRow[];reason?:string;rule?:string;profile?:{answered:number;complete:boolean;missing_required:string[]}};

/** Capture surface. `complete` is computed by the engine: every requested page and
 *  item arrived and nothing was truncated. A partial run is normal and is shown as
 *  such, never as coverage. */
export type ScrapeEngine={available:boolean;detail:string;version?:string|null;sessions?:boolean};
export type ScrapeSession={source:string;present:boolean;method?:string|null;source_url?:string|null;saved_at?:string|null;hosts?:string[];cookie_count?:number|null;expired?:boolean};
export type ScrapeRecipe={id:string;source:string;origin:string;start_url:string;auth:string;kind:string;cadence_hours:number;due?:boolean;reason?:string;path?:string;last_run?:{captured_at?:string;complete?:boolean;items_captured?:number;reason?:string}|null};
export type ScrapeStatus={root:string;recipes:ScrapeRecipe[];recipe_errors:Array<{path:string;error:string}>;due:string[];sessions:ScrapeSession[];engines:Record<string,ScrapeEngine>;challenge:{configured:string;default:string;policies:string[];solver:{configured:boolean;provider?:string};rule:string};captured_postings:number;last_run?:Record<string,unknown>|null};
export type ScrapeWritten={url:string;title?:string;driver?:string;path?:string;written?:boolean;duplicate?:boolean;company?:string;flaggged?:boolean};
export type ScrapeCapture={ok:boolean;complete:boolean;url:string;reason?:string|null;driver?:string;title?:string;source?:string;posting?:string;duplicate?:boolean;session?:{used?:boolean;source?:string};challenge?:Record<string,unknown>;robots?:Record<string,unknown>;duration_ms?:number};
export type ScrapeRun={recipe:string;complete:boolean;items:number;items_captured:number;attempted?:number;truncated?:boolean;capped?:boolean;reason?:string;written:ScrapeWritten[];duplicates:ScrapeWritten[];failures:Array<{stage:string;url:string;error:string}>;drivers?:string[];duration_ms?:number};
export type TemplateFields={template:string;fields:string[]};
export type TemplateFill={written?:boolean;output:string;template:string;fields:number;declared:string[];replaced:Record<string,number>;mode:Record<string,number>;unused:string[];leftovers:string[];paragraphs_touched:number;bytes?:number};
export type TemplateVerify={passed:boolean;checks:Array<{id:string;ok:boolean;detail:string}>;declared:string[]};
/** `GET /api/trash` returns three buckets and only the first is restorable:
 *  `entries` name the workspace-relative path a restore writes back to, while
 *  `external` (backups of files outside the workspace) and `unmanaged` (a
 *  `render-backup-*` PDF has no honest reverse) are reported, never offered. */
export type TrashEntry={rel:string;trash_rel:string;name:string;size:number;mtime_ns?:number;trashed_at:string|null};
export type TrashRow={name:string;trash_rel:string;rel:string|null;size:number;mtime_ns?:number;trashed_at:string|null};
export type TrashRetention={retention_days:number;source:string;enabled:boolean;config_file:string;environment_variable:string;warnings?:string[]};
export type PruneRow={entry:string;age_days?:number;files?:number;bytes?:number;trashed_at?:string;purged?:boolean;quarantined?:boolean;reason:string};
export type PruneReport={retention_days:number;retention_source:string;enabled:boolean;dry_run:boolean;now:string;cutoff:string|null;removed:PruneRow[];kept:PruneRow[];skipped:PruneRow[];quarantined?:string[];removed_count:number;purged_count:number;kept_count:number;skipped_count:number;entries_remaining:number;freed_bytes:number;warnings:string[];reason:string;exceptional?:boolean;error?:string};
export type TrashListing={entries:TrashEntry[];external:TrashRow[];unmanaged:TrashRow[];root:string;retention:TrashRetention;startup_prune:PruneReport;last_prune:PruneReport|null};

const tokenKey='dossier-token';
// The shell (GET /) sets an HttpOnly, SameSite=Lax cookie, and that is how every API call is
// authorised. A `?token=` on the page URL used to be copied into sessionStorage as a second
// path; it is gone for the same reason the API stopped accepting a query token — a credential
// in a URL reaches history, the Referer and the access log. A token can still be supplied per
// call with `authHeaders()` below, which no browser code path does by default.
const token=()=>sessionStorage.getItem(tokenKey)||'';
const authHeaders=():HeadersInit=>token()?{Authorization:`Bearer ${token()}`}:{};
// The bearer token never goes in a URL. It used to be appended to /api/raw, /api/render and
// /api/events, which put it in the address bar, browser history, the Referer of a followed
// link and the server's access log — the `token-never-leaks` gate says it must not. The
// SameSite=Lax cookie the shell is served with authorises all three requests instead.

/** A failed API call, carrying the status so the caller can say what happened. */
export class ApiError extends Error{
  status:number;
  detail:string;
  constructor(status:number,detail:string){
    super(detail?`${status} ${detail}`:`${status}`);
    this.name='ApiError';
    this.status=status;
    this.detail=detail;
  }
}

export type Fault={title:string;next:string};
export const isConflict=(error:unknown)=>error instanceof ApiError&&error.status===409;

/** Cause and next move, in the interface's voice (DESIGN.md:105). No raw stacks. */
export function fault(error:unknown,what:string):Fault{
  if(error instanceof ApiError){
    const detail=error.detail?` ${error.detail}`:'';
    if(error.status===401)return{title:'The Dossier API rejected this request (401).',next:'Open the app from the address the server printed so the per-run token is loaded, then retry.'};
    if(error.status===403)return{title:'The API refused this request’s origin (403).',next:'Open Dossier on 127.0.0.1 or localhost rather than another hostname.'};
    if(error.status===404)return{title:`Not found on disk (404).${detail}`,next:'Refresh the tree — the file was moved, renamed or deleted outside Dossier.'};
    if(error.status===400)return{title:`The API rejected the request (400).${detail}`,next:'Check the values in the form and try again.'};
    if(error.status===428)return{title:'This action needs a confirmation (428).',next:'Press the action again and choose Run in the confirmation row.'};
    if(error.status>=500)return{title:`The Dossier API failed (${error.status}).${detail}`,next:'The traceback is in the server console; reload to rebuild the index.'};
    return{title:`${what} failed (${error.status}).${detail}`,next:'Try again; if it keeps failing, check the server console.'};
  }
  const message=error instanceof Error?error.message:String(error);
  if(/failed to fetch|networkerror|load failed|err_connection/i.test(message))return{title:'The Dossier API is not reachable.',next:'Start the server (dossier web) and press Retry.'};
  return{title:`${what} failed.`,next:'Try again; if it keeps failing, check the server console.'};
}

async function readDetail(response:Response):Promise<string>{
  try{
    const body=await response.clone().json() as {detail?:unknown};
    if(typeof body?.detail==='string')return body.detail;
    if(body?.detail)return JSON.stringify(body.detail);
  }catch{/* not JSON */}
  try{return (await response.text()).slice(0,300)}catch{return ''}
}

const request=async<T>(url:string,init:RequestInit={}):Promise<T>=>{
  const headers=new Headers(init.headers);
  Object.entries(authHeaders()).forEach(([key,value])=>headers.set(key,String(value)));
  const response=await fetch(url,{...init,headers});
  if(!response.ok)throw new ApiError(response.status,await readDetail(response));
  if(response.status===204)return undefined as T;
  return response.json() as Promise<T>;
};
const requestText=async(url:string):Promise<string>=>{
  const response=await fetch(url,{headers:authHeaders()});
  if(!response.ok)throw new ApiError(response.status,await readDetail(response));
  return response.text();
};

/** Ask before rendering a URL in an iframe or an <img>. A failed /api/render or
 *  /api/raw used to surface as a raw FastAPI JSON body inside the document pane. */
export const checkUrl=async(url:string):Promise<void>=>{
  const response=await fetch(url,{headers:authHeaders()});
  if(!response.ok)throw new ApiError(response.status,await readDetail(response));
};

export type PanelFinding={reviewer:string;verdict:string;line:number|null;quote:string;why:string;fix:string;weight:number};
export type PanelSeat={id:string;name:string;asks:string;score:number;findings:PanelFinding[]};
export type PanelReport={score:number;verdict:string;lines:number;words:number;has_posting:boolean;
 seats:PanelSeat[];plan:Array<{order:number;seat:string;line:number|null;quote:string;why:string;rewrite:string}>};
export const api={
 fileTree:(dir='')=>request<FileNode[]>(`/api/tree?dir=${encodeURIComponent(dir)}`),
 health:()=>request<Health>('/api/health'),
 trajectory:()=>request<TrajectoryGraph>('/api/tree?view=trajectory'),
 treeUpsert:(node:TreeNodeInput)=>request<TrajectoryNode>('/api/tree/nodes',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(node)}),
 treeLink:(parent_id:string,child_id:string)=>request<TrajectoryLink>('/api/tree/links',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({parent_id,child_id})}),
 treeSync:()=>request<Record<string,unknown>>('/api/tree/sync',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({})}),
 treeNextPacket:(query:string)=>request<Record<string,unknown>>('/api/tree/packet',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({limit:40,context_limit:200,query})}),
 treeExport:(format:'ascii'|'mermaid')=>requestText(`/api/tree/export?format=${format}`),
 file:(rel:string)=>request<{content:string;stamp:FileStamp}>(`/api/file?rel=${encodeURIComponent(rel)}`),
 save:(rel:string,content:string,expect?:FileStamp)=>request<{rel:string;stamp:FileStamp}>('/api/file',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({rel,content,expect})}),
 bundle:(rel:string)=>request<Bundle>(`/api/bundle?rel=${encodeURIComponent(rel)}`),
 search:(query:string)=>request<Array<{rel:string;snippet?:string;kind?:string}>>(`/api/search?q=${encodeURIComponent(query)}`),
 raw:(rel:string)=>`/api/raw?rel=${encodeURIComponent(rel)}`,
 /* A GET serves the cached PDF; a miss (409) is built by the POST, then fetched again.
    The GET must stay cheap: it is an <iframe src>, not a job. */
 render:async(rel:string):Promise<string>=>{
   const url=`/api/render?rel=${encodeURIComponent(rel)}`;
   const probe=await fetch(url,{credentials:'same-origin'});
   if(probe.status===409){
     await fetch('/api/render',{method:'POST',credentials:'same-origin',
       headers:{'Content-Type':'application/json'},body:JSON.stringify({rel})});
   }
   return url;
 },
 convertRoutes:(rel:string)=>request<{rel:string;ext:string;routes:Array<{target:string;fidelity:string;requires:string|null}>}>(`/api/convert/routes?rel=${encodeURIComponent(rel)}`),
 exportFile:(rel:string,target:string)=>request<ExportResult>(`/api/export?rel=${encodeURIComponent(rel)}&target=${encodeURIComponent(target)}`),
 panel:(resume:string,posting='',role='')=>request<PanelReport>(
   `/api/panel?resume=${encodeURIComponent(resume)}&posting=${encodeURIComponent(posting)}&role=${encodeURIComponent(role)}`),
 actions:()=>request<Action[]>('/api/actions'),
 runAction:(id:string,rel:string,confirmed=false)=>request<{returncode:number;stdout:string;stderr:string}>('/api/actions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id,rel,confirmed})}),
 jobs:()=>request<any[]>('/api/jobs'),
 history:()=>request<any[]>('/api/jobs/history'),
 due:()=>request<CadenceEntry[]>('/api/jobs/due'),
 feeds:()=>request<FeedCatalog>('/api/jobs/feeds'),
 audit:()=>request<Audit>('/api/audit'),
 handoff:()=>request<{packet:Record<string,unknown>;prompt:string}>('/api/ai/handoff'),
 sources:()=>request<SourceLedger>('/api/sources'),
 track:()=>request<TrackSummary>('/api/track'),
 cadence:(overdue=false)=>request<CadenceReport>(`/api/track/cadence?overdue=${overdue?'true':'false'}`),
 corpus:(limit=40)=>request<CorpusReport>(`/api/corpus?limit=${limit}`),
 verify:(params:{base?:string;candidate?:string;pdf?:string;expected_pages?:number})=>{
   const q=new URLSearchParams();
   if(params.base)q.set('base',params.base);
   if(params.candidate)q.set('candidate',params.candidate);
   if(params.pdf)q.set('pdf',params.pdf);
   if(params.expected_pages)q.set('expected_pages',String(params.expected_pages));
   return request<VerifyReport>(`/api/verify?${q.toString()}`);
 },
 trash:()=>request<TrashListing>(`/api/trash`), trashRestore:(entry:TrashEntry)=>request<{restored?:boolean;rel?:string;path?:string}>(`/api/trash/restore`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({rel:entry.rel,trash_rel:entry.trash_rel})}),
 trashPrune:(dryRun=false)=>request<PruneReport>(`/api/trash/prune`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({dry_run:dryRun})}),
 eventsUrl:()=>'/api/events',
 identity:()=>request<IdentityState>('/api/identity'),
 identityAnswers:(answers:Record<string,string>)=>request<{saved:string[];complete:boolean;missing_required:string[];fields:number}>('/api/identity/answers',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({answers})}),
 identityWrite:(name?:string)=>request<{path:string;fields:number;missing_required:string[]}>('/api/identity/write',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name})}),
 match:(limit=20,minBand='')=>request<MatchReport>(`/api/match?limit=${limit}${minBand?`&min_band=${minBand}`:''}`),
 scrapeStatus:()=>request<ScrapeStatus>('/api/scrape'),
 scrapeRecipes:()=>request<{recipes:ScrapeRecipe[];errors:Array<{path:string;error:string}>}>('/api/scrape/recipes'),
 scrapeCapture:(body:{url:string;source?:string;session?:boolean;challenge?:string;driver?:string;await_seconds?:number;refresh?:boolean;screenshot?:boolean})=>request<ScrapeCapture>('/api/scrape/capture',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}),
 scrapeRun:(body:{recipe:string;limit?:number;pages?:number;challenge?:string})=>request<ScrapeRun>('/api/scrape/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}),
 templateFields:(template:string)=>request<TemplateFields>(`/api/tailor/fields?template=${encodeURIComponent(template)}`),
 fillTemplate:(body:{template:string;out:string;spec:{fields:Record<string,string>;replace?:Record<string,string>};allow_leftovers?:boolean})=>request<TemplateFill>('/api/tailor/template',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}),
 verifyTemplateInline:(body:{template:string;candidate:string;spec:{fields:Record<string,string>}})=>request<TemplateVerify>('/api/verify/template',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}),
 verifyTemplate:(template:string,candidate:string,spec:string)=>request<TemplateVerify>(`/api/verify/template?template=${encodeURIComponent(template)}&candidate=${encodeURIComponent(candidate)}&spec=${encodeURIComponent(spec)}`),
};
export type AgentMode={id:string;label:string;stage:string;kind:string;summary:string};
export type AgentGate={id:string;rule:string;enforced_by:string;never:string};
export type AgentContract={schema_version:string;summary:string;stages:Array<{id:string;label:string;intent:string}>;modes:AgentMode[];gates:AgentGate[];artifacts:Array<{name:string;role:string;required:boolean}>};
export type AgentUnit={mode:string;label:string;stage:string;kind:string;reason:string;summary:string;needs_user?:boolean;blocking?:boolean;targets?:string[]};
export type AgentStatus={root:string;updated?:string|null;sessions:number;last?:unknown;blockers:string[];counts:Record<string,number>;next:AgentUnit;recent:Array<{at:string;mode:string;status:string;artifacts:string[]}>};
export type WorkspaceState={root:string;name:string;counts:Record<string,number>;identity_doc?:{rel:string}|null;corpus:Record<string,any>;tracker:Record<string,any>;coverage:Record<string,any>;ready:string[];blockers:string[]};
export type CommitResult={accepted:boolean;problems?:string[];expected?:string[];recorded?:Record<string,unknown>;next?:AgentUnit;sessions?:number};
export type AdapterReport={packs:string[];current:Record<string,boolean>};
export const agentApi={
  contract:()=>request<AgentContract>('/api/agent/manifest'),
  status:()=>request<AgentStatus>('/api/agent/status'),
  route:(q:string)=>request<{request:string;matches:Array<AgentMode&{score:number}>;confident:boolean}>(`/api/agent/route?q=${encodeURIComponent(q)}`),
  brief:(mode:string)=>requestText(`/api/agent/brief?mode=${encodeURIComponent(mode)}&format=markdown`),
  prompt:()=>requestText('/api/agent/prompt'),
  adapters:()=>request<AdapterReport>('/api/agent/adapters'),
  commit:(handback:Record<string,unknown>)=>request<CommitResult>('/api/agent/commit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(handback)}),
  workspace:()=>request<WorkspaceState>('/api/workspace'),
  doctor:()=>request<{verdict:string;capabilities:Record<string,boolean>;blockers:string[];platform:Record<string,string>}>('/api/doctor'),
};
