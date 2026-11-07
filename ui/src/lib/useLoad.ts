import {useCallback,useEffect,useRef,useState} from 'react';

/** Loading, ready and failed are three different states — never one empty state. */
export type Loadable<T>={status:'loading'}|{status:'ready';data:T}|{status:'failed';error:unknown};

export function useLoad<T>(load:()=>Promise<T>,deps:unknown[]):{state:Loadable<T>;reload:()=>void}{
  const [state,setState]=useState<Loadable<T>>({status:'loading'});
  const [version,setVersion]=useState(0);
  const latest=useRef(load);
  latest.current=load;
  useEffect(()=>{
    let live=true;
    setState(current=>current.status==='ready'?current:{status:'loading'});
    latest.current().then(data=>{if(live)setState({status:'ready',data})})
      .catch(error=>{if(live)setState({status:'failed',error})});
    return()=>{live=false};
    // eslint-disable-next-line react-hooks/exhaustive-deps
  },[version,...deps]);
  const reload=useCallback(()=>setVersion(value=>value+1),[]);
  return {state,reload};
}
