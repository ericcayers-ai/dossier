import {FormEvent, useCallback, useEffect, useMemo, useState} from 'react';
import {api,fault,TrajectoryGraph,TrajectoryNode,TrajectoryNodeType,TrajectoryState,TreeNodeInput} from '../lib/api';

/* One error vocabulary for the whole pane: cause plus the next move, never the
   raw `String(reason)` a user cannot act on ("TypeError: Failed to fetch"). */
const describe=(reason:unknown,what:string)=>{const {title,next}=fault(reason,what);return `${title} ${next}`};

const NODE_TYPES:TrajectoryNodeType[]=['experience','contact','touchpoint','meeting','opportunity','milestone'];
const TYPE_LABEL:Record<TrajectoryNodeType,string>={experience:'Experiences',contact:'Contacts',touchpoint:'Emails & touchpoints',meeting:'Meetings',opportunity:'Opportunities',milestone:'Milestones'};
const STATES:TrajectoryState[]=['planned','active','complete','cancelled'];
const fitOrder:Record<string,number>={High:0,Medium:1,Low:2,Skip:3};
const asText=(value:unknown)=>typeof value==='string'?value:value==null?'':String(value);
const record=(value:unknown):Record<string,unknown>=>value&&typeof value==='object'&&!Array.isArray(value)?value as Record<string,unknown>:{};

export default function TrajectoryPane(){
  const [graph,setGraph]=useState<TrajectoryGraph|null>(null);
  const [loading,setLoading]=useState(true);
  const [saving,setSaving]=useState(false);
  const [query,setQuery]=useState('');
  const [error,setError]=useState('');
  const [notice,setNotice]=useState('');
  const [exportText,setExportText]=useState('');
  const [packetText,setPacketText]=useState('');
  const [nodeId,setNodeId]=useState('');
  const [nodeType,setNodeType]=useState<TrajectoryNodeType>('experience');
  const [title,setTitle]=useState('');
  const [state,setState]=useState<TrajectoryState>('planned');
  const [date,setDate]=useState('');
  const [details,setDetails]=useState('');
  const [parentId,setParentId]=useState('');
  const [childId,setChildId]=useState('');
  const [opportunityLimit,setOpportunityLimit]=useState(40);
  const [opportunityCoverage,setOpportunityCoverage]=useState<{included:number;omitted:number}>({included:0,omitted:0});

  const reload=useCallback(async()=>{
    setLoading(true);
    try{setGraph(await api.trajectory());setError('')}
    catch(reason){setError(describe(reason,'Reading the trajectory graph'));setGraph(null)}
    finally{setLoading(false)}
  },[]);
  useEffect(()=>{void reload()},[reload]);

  const visibleNodes=useMemo(()=>{
    if(!graph)return [];
    const needle=query.trim().toLowerCase();
    return graph.nodes.filter(node=>!needle||[node.title,asText(node.data.employer),asText(node.data.location),node.id].join(' ').toLowerCase().includes(needle));
  },[graph,query]);
  const nodesById=useMemo(()=>new Map((graph?.nodes||[]).map(node=>[node.id,node])),[graph]);
  const linksByChild=useMemo(()=>{
    const result=new Map<string,string[]>();
    graph?.links.forEach(link=>result.set(link.child_id,[...(result.get(link.child_id)||[]),link.parent_id]));
    return result;
  },[graph]);
  const linksByParent=useMemo(()=>{
    const result=new Map<string,string[]>();
    graph?.links.forEach(link=>result.set(link.parent_id,[...(result.get(link.parent_id)||[]),link.child_id]));
    return result;
  },[graph]);
  const groups=useMemo(()=>NODE_TYPES.map(type=>({type,nodes:visibleNodes.filter(node=>node.type===type).sort((a,b)=>{
    if(type==='opportunity')return (fitOrder[asText(a.data.fit)]??4)-(fitOrder[asText(b.data.fit)]??4)||a.title.localeCompare(b.title)||a.id.localeCompare(b.id);
    return (a.date||'').localeCompare(b.date||'')||a.title.localeCompare(b.title)||a.id.localeCompare(b.id);
  })})),[visibleNodes]);

  const runSync=async()=>{
    setSaving(true);setError('');setNotice('');
    try{
      const result=await api.treeSync();
      await reload();
      const jobs=Number(result.jobs_seen)||0;
      const matched=Number(result.tracker_matched)||0;
      const separate=Number(result.tracker_separate)||0;
      const ambiguous=Number(result.tracker_ambiguous)||0;
      setNotice(`Read ${jobs} corpus jobs and ${Number(result.tracker_rows)||0} tracker rows; ${matched} uniquely linked, ${separate} kept separate, ${ambiguous} ambiguous. Added ${Number(result.nodes_added)||0} nodes; source files were not changed.`);
    }catch(reason){setError(describe(reason,'Syncing workspace sources'))}
    finally{setSaving(false)}
  };
  const addNode=async(event:FormEvent<HTMLFormElement>)=>{
    event.preventDefault();setSaving(true);setError('');setNotice('');
    const payload:TreeNodeInput={type:nodeType,title:title.trim(),state,details};
    if(nodeId.trim())payload.id=nodeId.trim();
    if(date)payload.date=date;
    try{
      const created=await api.treeUpsert(payload);
      await reload();setTitle('');setNodeId('');setDetails('');setDate('');setState('planned');
      setNotice(`Saved ${created.type}: ${created.title}.`);
    }catch(reason){setError(describe(reason,'Saving that node'))}
    finally{setSaving(false)}
  };
  const changeState=async(node:TrajectoryNode,next:TrajectoryState)=>{
    setSaving(true);setError('');setNotice('');
    try{
      await api.treeUpsert({id:node.id,state:next} as TreeNodeInput);
      await reload();setNotice(`Updated ${node.title} to ${next}.`);
    }catch(reason){setError(describe(reason,'Updating that node'))}
    finally{setSaving(false)}
  };
  const addLink=async(event:FormEvent<HTMLFormElement>)=>{
    event.preventDefault();setSaving(true);setError('');setNotice('');
    try{
      await api.treeLink(parentId.trim(),childId.trim());
      await reload();setNotice('Sequential prerequisite linked.');
    }catch(reason){setError(describe(reason,'Creating that link'))}
    finally{setSaving(false)}
  };
  const exportTree=async(format:'ascii'|'mermaid')=>{
    setError('');
    try{setExportText(await api.treeExport(format));setNotice(`${format==='ascii'?'ASCII':'Mermaid'} export ready below.`)}
    catch(reason){setError(describe(reason,'Exporting the tree'))}
  };
  const generatePacket=async()=>{
    if(!graph)return;
    setError('');
    try{
      const packet=await api.treeNextPacket(query.trim());
      const coverage=record(packet.sourceCoverage);
      setOpportunityCoverage({included:Number(coverage.includedOpportunities)||0,omitted:Number(coverage.omittedOpportunities)||0});
      const text=JSON.stringify(packet,null,2);
      setPacketText(text);
      try{await navigator.clipboard.writeText(text);setNotice('Structured, bounded next-branch packet copied. Review the JSON below before sharing it with a model.')}
      catch{setNotice('Packet is ready below. Clipboard access was unavailable; select and copy the JSON.')}
    }catch(reason){setError(describe(reason,'Generating the next-branch packet'))}
  };

  if(loading&&!graph)return <section className="trajectory-pane" aria-busy="true"><h1>Trajectory</h1><p role="status">Loading the local career graph…</p></section>;
  if(!graph)return <section className="trajectory-pane"><h1>Trajectory</h1><div className="trajectory-message" role="alert">{error||'The trajectory graph is unavailable.'}<button type="button" onClick={()=>void reload()}>Retry</button></div></section>;

  const actionable=graph.nodes.filter(node=>node.actionable).length;
  const blocked=graph.nodes.filter(node=>node.blocked_by?.length).length;
  return <section className="trajectory-pane" aria-labelledby="trajectory-title">
    <header className="trajectory-head">
      <div><h1 id="trajectory-title">Trajectory</h1><p>Build evidence-backed pathways from experience through relationships and opportunities. Sources are read-only; status changes are explicit.</p></div>
      <div className="trajectory-counts" aria-label="Graph summary"><span><b>{graph.nodes.length}</b> nodes</span><span><b>{graph.links.length}</b> links</span><span><b>{actionable}</b> actionable</span><span><b>{blocked}</b> blocked</span></div>
    </header>

    <div className="trajectory-toolbar" aria-label="Trajectory actions">
      <button type="button" onClick={()=>void runSync()} disabled={saving}>{saving?'Working…':'Sync workspace sources'}</button>
      <button type="button" onClick={()=>void exportTree('ascii')}>Export ASCII</button>
      <button type="button" onClick={()=>void exportTree('mermaid')}>Export Mermaid</button>
      <button type="button" onClick={()=>void generatePacket()} disabled={!graph.nodes.length}>Generate Next Branch</button>
      <label className="trajectory-search">Find nodes<input type="search" value={query} onChange={event=>setQuery(event.target.value)} placeholder="Title, employer, location or ID" /></label>
    </div>

    {notice&&<p className="trajectory-notice" role="status">{notice}</p>}
    {error&&<p className="trajectory-error" role="alert">{error}</p>}
    {packetText&&<p className="trajectory-notice" role="status">Packet contains {opportunityCoverage.included} opportunity records; {opportunityCoverage.omitted} matching records omitted by the explicit limit.</p>}

    <div className="trajectory-workspace">
      <div className="trajectory-groups" aria-label="Career pathway groups">
        {groups.map(group=>{
          const visible=group.type==='opportunity'&&!query?group.nodes.slice(0,opportunityLimit):group.nodes;
          const isCollapsed=group.type==='opportunity'&&!query&&group.nodes.length>opportunityLimit;
          return <details className="trajectory-group" key={group.type} open={!isCollapsed}>
            <summary><span>{TYPE_LABEL[group.type]}</span><span className="trajectory-group-count">{group.nodes.length}</span></summary>
            <div className="trajectory-node-list">
              {visible.length?visible.map(node=>{
                const parents=(linksByChild.get(node.id)||[]).map(id=>nodesById.get(id)).filter((item):item is TrajectoryNode=>Boolean(item));
                const children=(linksByParent.get(node.id)||[]).map(id=>nodesById.get(id)).filter((item):item is TrajectoryNode=>Boolean(item));
                const tracker=record(node.data.tracker);
                const summaryMeta=[asText(node.data.employer),asText(node.data.location),node.data.fit?`Fit ${asText(node.data.fit)}`:'',asText(node.data.source)].filter((value):value is string=>Boolean(value));
                return <article className={`trajectory-node state-${node.state}`} key={node.id}>
                  <div className="trajectory-node-top"><span className="trajectory-node-type">{node.type}</span><label className="trajectory-state-control">State<select aria-label={`State for ${node.title}`} value={node.state} disabled={saving} onChange={event=>void changeState(node,event.target.value as TrajectoryState)}>{STATES.map(value=><option value={value} key={value}>{value}</option>)}</select></label></div>
                  <h3>{node.title}</h3>
                  <code className="trajectory-id">{node.id}</code>
                  {node.date&&<p className="trajectory-meta">Date: {node.date}</p>}
                  {summaryMeta.length>0&&<p className="trajectory-meta trajectory-meta-list">{summaryMeta.map(value=><span key={value}>{value}</span>)}</p>}
                  {typeof tracker.status==='string'&&<p className="trajectory-meta">Tracker status (source record): {tracker.status}</p>}
                  {node.blocked_by?.length? <p className="trajectory-blocked">Blocked by: {node.blocked_by.map(id=>nodesById.get(id)?.title||id).join(', ')}</p>:node.actionable&&<p className="trajectory-ready">Ready when you choose to proceed</p>}
                  {parents.length>0&&<p className="trajectory-relation"><b>Follows:</b> {parents.map(item=>item.title).join(', ')}</p>}
                  {children.length>0&&<p className="trajectory-relation"><b>Branches to:</b> {children.map(item=>item.title).join(', ')}</p>}
                  {node.details&&<p className="trajectory-details">{node.details}</p>}
                  {node.artifacts.length>0&&<details className="trajectory-artifacts"><summary>Attached artifacts ({node.artifacts.length})</summary><ul>{node.artifacts.map(path=><li key={path}><a href={api.raw(path)} target="_blank" rel="noreferrer">{path}</a></li>)}</ul></details>}
                  <div className="trajectory-node-actions"><button type="button" onClick={()=>setParentId(node.id)} aria-label={`Use ${node.title} as prerequisite`}>Use as prerequisite</button><button type="button" onClick={()=>setChildId(node.id)} aria-label={`Use ${node.title} as next step`}>Use as next step</button></div>
                </article>;
              }):<p className="trajectory-empty">No {TYPE_LABEL[group.type].toLowerCase()} yet.</p>}
              {group.type==='opportunity'&&group.nodes.length>visible.length&&<button type="button" className="trajectory-more" onClick={()=>setOpportunityLimit(limit=>limit+100)}>Show {Math.min(100,group.nodes.length-visible.length)} more opportunities ({group.nodes.length-visible.length} remaining)</button>}
            </div>
          </details>;
        })}
      </div>

      <aside className="trajectory-forms" aria-label="Create nodes and links">
        <form className="trajectory-form" onSubmit={event=>void addNode(event)}>
          <h2>Add a node</h2>
          <label>Type<select value={nodeType} onChange={event=>setNodeType(event.target.value as TrajectoryNodeType)}>{NODE_TYPES.map(type=><option value={type} key={type}>{type}</option>)}</select></label>
          <label>Title<input required maxLength={240} value={title} onChange={event=>setTitle(event.target.value)} /></label>
          <label>Optional ID<input value={nodeId} onChange={event=>setNodeId(event.target.value)} placeholder="Generated if blank" /></label>
          <div className="trajectory-form-row"><label>State<select value={state} onChange={event=>setState(event.target.value as TrajectoryState)}>{STATES.map(value=><option value={value} key={value}>{value}</option>)}</select></label><label>Date<input type="date" value={date} onChange={event=>setDate(event.target.value)} /></label></div>
          <label>Evidence or notes<textarea maxLength={5000} rows={3} value={details} onChange={event=>setDetails(event.target.value)} /></label>
          <button type="submit" disabled={saving||!title.trim()}>Save node</button>
        </form>
        <form className="trajectory-form" onSubmit={event=>void addLink(event)}>
          <h2>Link sequential steps</h2>
          <p>Every parent must be complete before its child can become active or complete.</p>
          <label>Prerequisite node ID<input required value={parentId} onChange={event=>setParentId(event.target.value)} /></label>
          <label>Next node ID<input required value={childId} onChange={event=>setChildId(event.target.value)} /></label>
          <button type="submit" disabled={saving||!parentId.trim()||!childId.trim()}>Create link</button>
        </form>
      </aside>
    </div>

    {exportText&&<details className="trajectory-output" open><summary>Tree export</summary><pre>{exportText}</pre></details>}
    {packetText&&<details className="trajectory-output" open><summary>Next-branch packet (JSON)</summary><textarea aria-label="Structured next-branch packet" readOnly rows={10} value={packetText}/></details>}
    {graph.nodes.length===0&&<p className="trajectory-footnote">Sync reads the aggregate job corpus and job-history tracker into this workspace graph. It does not change source documents or infer that a draft was submitted.</p>}
  </section>;
}
