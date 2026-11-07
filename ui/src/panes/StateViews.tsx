import type {ReactNode} from 'react';
import {fault} from '../lib/api';

/** Reading is a state, not an empty result.
 *
 *  The skeleton reserves the height the content will take, so a pane does not
 *  jump when the answer arrives (CLS), and it is `aria-busy` rather than a
 *  spinner that hides the shape of what is coming.
 */
export function Loading({what,rows=3}:{what:string;rows?:number}):ReactNode{
  return <div className="loading" role="status" aria-busy="true" aria-label={`Reading ${what}`}>
    <span className="sr-only">{`Reading ${what}…`}</span>
    {Array.from({length:rows}).map((_,index)=><span className="skeleton" key={index}/>)}
  </div>;
}

/** Nothing here yet, and what to do about it. An empty state invites an action. */
export function EmptyState({title,children}:{title:string;children?:ReactNode}):ReactNode{
  return <div className="empty-state">
    <p className="empty-state-title">{title}</p>
    {children&&<div className="empty-state-body">{children}</div>}
  </div>;
}

/** Failure says what happened and what to do next — never a raw `String(error)`. */
export function ErrorState({error,what,onRetry,inline=false}:{error:unknown;what:string;onRetry?:()=>void;inline?:boolean}):ReactNode{
  const {title,next}=fault(error,what);
  const body=<>
    <h2>{title}</h2>
    <p>{next}</p>
  </>;
  if(inline)return <div className="notice" role="alert"><b>{title}</b><p>{next}</p>{onRetry&&<button type="button" onClick={onRetry}>Retry</button>}</div>;
  return <div className="empty-panel" role="alert">{body}{onRetry&&<p><button type="button" className="primary" onClick={onRetry}>Retry</button></p>}</div>;
}
