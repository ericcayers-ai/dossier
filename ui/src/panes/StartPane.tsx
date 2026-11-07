import type {ReactNode} from 'react';
import {agentApi,api} from '../lib/api';
import type {IdentityState,WorkspaceState} from '../lib/api';
import {useLoad} from '../lib/useLoad';
import {count} from '../lib/copy';
import {ErrorState,Loading} from './StateViews';
import NextStep from './NextStep';

/** Start here: the one screen a newcomer needs.
 *
 *  Before this the app opened on a file browser whose only button ("Open Folder")
 *  went to the pane it was already showing, and the four things a job search
 *  actually consists of were spread across five areas and twelve panes named
 *  after the engine (`Capture`, `Identity`, `Build`, `Opportunity`). The folder
 *  resolver already reports all four (`/api/workspace`), so the screen states them
 *  in the order a person does them, says which one is done, and hands the reading
 *  of "what now" to the engine's own next unit — one primary action, one reason.
 *
 *  Nothing here decides anything: the steps are `workspace.counts`, the done-flags
 *  are engine facts, and the action is `agent status`. The pane adds vocabulary,
 *  not behaviour. */

type Step={id:string;title:string;detail:string;done:boolean;pane:string};

const LABEL:Record<string,string>={'files':'Folder',identity:'Identity',capture:'Capture',
  build:'Build'};

function stepsOf(workspace:WorkspaceState,identity:IdentityState|null):Step[]{
  const counts=workspace.counts??{};
  const files=Number(counts.files??0);
  const resumes=Number(counts.base_documents??0);
  const postings=Number(counts.postings??0);
  const built=Number(counts.artefacts??0);
  const answered=identity?identity.answered:0;
  const questions=identity?identity.questions:0;
  const resumeReady=resumes>0;
  const documentReady=resumeReady&&built>0;
  return [
    {id:'folder',title:'Your folder',pane:'files',done:files>0,
     detail:files>0?`${count(files,'file')} here, ready to read.`
       :'Empty. Put the folder you keep your job search in here.'},
    {id:'aim',title:'What you want',pane:'identity',done:Boolean(identity?.complete),
     detail:questions>0?`${answered} of ${questions} questions answered.`
       :'Not answered yet.'},
    {id:'postings',title:'Job ads',pane:'capture',done:postings>0,
     detail:postings>0?`${count(postings,'job ad')} saved.`
       :'Paste a link to one job ad and Dossier keeps a copy.'},
    {id:'document',title:'A tailored document',pane:'build',done:documentReady,
     detail:documentReady?`${count(built,'document')} built. The layout is your own.`
       :resumeReady?'Fill your own resume for one job. The layout never changes.'
       :'Blocked until your resume is in this folder.'},
  ];
}

export default function StartPane({onGo}:{onGo:(pane:string)=>void}):ReactNode{
  const workspace=useLoad<WorkspaceState>(()=>agentApi.workspace(),[]);
  const identity=useLoad<IdentityState>(()=>api.identity(),[]);
  const kind=workspace.state.status;
  const data=kind==='ready'?workspace.state.data:null;
  const steps=data?stepsOf(data,identity.state.status==='ready'?identity.state.data:null):[];
  const next=steps.find(step=>!step.done)?.id;
  const root=data?.root??'';
  /* The one fact that stops everything else: a job search can be run without
     answers and without postings, but not without the document that gets cloned. */
  const noResume=Boolean(data)&&Number(data?.counts?.base_documents??0)===0;

  return <div className="start-pane">
    <div className="audit-head">
      <div>
        <h1>Start here</h1>
        <p className="pane-purpose">Dossier turns one job ad into one tailored document you can send, then keeps track of what you sent.</p>
      </div>
    </div>

    {kind==='loading'?<Loading what="this folder" rows={4}/>
      :kind==='failed'?<ErrorState error={workspace.state.error} what="Reading this folder" onRetry={workspace.reload}/>
      :<>
        {noResume&&<p className="notice">No resume to build from yet. Dossier clones the <code>.docx</code> you send to employers, so put that file in this folder (its name needs to contain "resume" or "cv").</p>}

        {/* The engine's own answer to "what now", with its reason and its one action. */}
        <NextStep onGo={onGo}/>

        <h2>The four steps</h2>
        <ol className="steps">
          {steps.map((step,index)=><li key={step.id}
            className={`step${step.done?' done':''}${step.id===next?' next':''}`}>
            <span className="step-index" aria-hidden="true">{index+1}</span>
            <div className="step-body">
              <b>{step.title}</b>
              <span className="step-detail">{step.detail}</span>
            </div>
            <span className="step-state">{step.done?'Done':step.id===next?'Next':'Not yet'}</span>
            <button type="button" onClick={()=>onGo(step.pane)}>
              {`${step.done?'Review':'Open'} ${LABEL[step.pane]??step.pane}`}
            </button>
          </li>)}
        </ol>

        <section className="start-folder" aria-label="This folder">
          <h2>This folder</h2>
          <p className="sync-note"><code>{root}</code></p>
          <p className="pane-purpose">Dossier reads this folder and nothing else. No file leaves this machine.</p>
          <details className="sync-more">
            <summary>Use a different folder</summary>
            <p className="pane-purpose">Close Dossier, then start it on the folder where your job search lives:</p>
            <pre className="start-command">{'run.cmd "C:\\path\\to\\your job search"'}</pre>
            <p className="pane-purpose">Or, from a terminal: <code>{'dossier --root "C:\\path\\to\\your job search" --open'}</code></p>
          </details>
        </section>
      </>}
  </div>;
}
