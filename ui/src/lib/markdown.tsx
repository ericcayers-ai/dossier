import {useMemo} from 'react';
import type {ReactNode} from 'react';
import {GFM,parser} from '@lezer/markdown';
import {api} from './api';

/* The reading pane. CommonMark + GFM (tables, strikethrough, task lists,
   autolinks) parsed by the same Lezer parser the Markdown editor already
   bundles, then walked into real nested HTML. The previous renderer was three
   `startsWith` checks that emitted bare <li> with no <ul>. */

type MdNode={name:string;from:number;to:number;firstChild:MdNode|null;nextSibling:MdNode|null};

const MD_PARSER=parser.configure(GFM);
const MARKS=new Set(['HeaderMark','ListMark','TaskMarker','QuoteMark','EmphasisMark','CodeMark','LinkMark','TableDelimiter','URL','CodeInfo']);

function kids(node:MdNode):MdNode[]{const out:MdNode[]=[];for(let child=node.firstChild;child;child=child.nextSibling)out.push(child);return out}
function childNamed(node:MdNode,name:string):MdNode|null{for(const child of kids(node))if(child.name===name)return child;return null}
function slice(text:string,node:MdNode):string{return text.slice(node.from,node.to)}

function contentRange(node:MdNode):[number,number]{
  const list=kids(node);
  let from=node.from;
  let to=node.to;
  let start=0;
  let end=list.length-1;
  while(start<list.length&&MARKS.has(list[start].name)){from=list[start].to;start+=1}
  while(end>=0&&MARKS.has(list[end].name)){to=list[end].from;end-=1}
  return [from,to];
}

function safeHref(href:string):string|undefined{
  const value=href.trim();
  if(/^(https?:|mailto:|tel:|#)/i.test(value))return value;
  if(/^[a-z][a-z0-9+.-]*:/i.test(value))return undefined; // javascript:, vbscript:, data: …
  return value;
}
function localImage(src:string,base:string):string|undefined{
  const value=src.trim();
  if(!value)return undefined;
  if(/^(https?:|data:image\/)/i.test(value))return value;
  if(/^[a-z][a-z0-9+.-]*:/i.test(value))return undefined;
  const clean=value.replace(/^\.\//,'');
  return api.raw(`${base}${clean}`);
}

export function MarkdownDoc({text,base=''}:{text:string;base?:string}):ReactNode{
  const rendered=useMemo(()=>{
    let sequence=0;
    const key=()=>`md-${sequence++}`;

    function range(parent:MdNode,from:number,to:number):ReactNode[]{
      const out:ReactNode[]=[];
      let position=from;
      for(const child of kids(parent)){
        if(child.to<=from||child.from>=to)continue;
        if(child.from>position)out.push(text.slice(position,child.from));
        out.push(inline(child));
        position=Math.max(position,child.to);
      }
      if(position<to)out.push(text.slice(position,to));
      return out;
    }

    function inline(node:MdNode):ReactNode{
      const [from,to]=contentRange(node);
      switch(node.name){
        case 'Emphasis':return <em key={key()}>{range(node,from,to)}</em>;
        case 'StrongEmphasis':return <strong key={key()}>{range(node,from,to)}</strong>;
        case 'Strikethrough':return <del key={key()}>{range(node,from,to)}</del>;
        case 'InlineCode':return <code key={key()}>{text.slice(from,to)}</code>;
        case 'Escape':return <span key={key()}>{slice(text,node).replace(/^\\(.)/,'$1')}</span>;
        case 'HardBreak':return <br key={key()}/>;
        case 'Link':{
          const url=childNamed(node,'URL');
          const marks=kids(node).filter(item=>item.name==='LinkMark');
          if(url&&marks.length>=2){
            const href=safeHref(slice(text,url));
            const label=range(node,marks[0].to,marks[1].from);
            if(href)return <a key={key()} href={href} rel="noreferrer noopener" target="_blank">{label}</a>;
            return <span key={key()}>{label}</span>;
          }
          return <span key={key()}>{range(node,from,to)}</span>;
        }
        case 'Image':{
          const url=childNamed(node,'URL');
          const marks=kids(node).filter(item=>item.name==='LinkMark');
          const source=url?slice(text,url):'';
          const alt=marks.length>=2?text.slice(marks[0].to,marks[1].from):source;
          const resolved=localImage(source,base);
          if(!resolved)return <span key={key()}>{alt}</span>;
          return <img key={key()} src={resolved} alt={alt} loading="lazy"/>;
        }
        default:
          if(node.firstChild)return <span key={key()}>{range(node,from,to)}</span>;
          return <span key={key()}>{text.slice(node.from,node.to)}</span>;
      }
    }

    function table(node:MdNode):ReactNode{
      const list=kids(node);
      const delimiter=list.find(item=>item.name==='TableDelimiter'&&item.from>node.from);
      const alignments:Array<'left'|'right'|'center'|undefined>=(delimiter?slice(text,delimiter):'').split('|').filter(part=>part.trim()!=='').map(part=>{
        const value=part.trim();
        const left=value.startsWith(':');
        const right=value.endsWith(':');
        return left&&right?'center':right?'right':left?'left':undefined;
      });
      const header=list.find(item=>item.name==='TableHeader');
      const rows=list.filter(item=>item.name==='TableRow');
      const cellsOf=(row:MdNode)=>kids(row).filter(item=>item.name==='TableCell');
      const headerCells=header?cellsOf(header):[];
      const style=(column:number)=>({textAlign:alignments[column]});
      return <table key={key()}>
        {headerCells.length>0&&<thead><tr>{headerCells.map((cell,column)=><th key={key()} style={style(column)}>{range(cell,cell.from,cell.to)}</th>)}</tr></thead>}
        <tbody>{rows.map(row=>{
          const cells=cellsOf(row);
          return <tr key={key()}>{Array.from({length:Math.max(cells.length,headerCells.length)}).map((_,column)=>cells[column]
            ?<td key={key()} style={style(column)}>{range(cells[column],cells[column].from,cells[column].to)}</td>
            :<td key={key()}/>)}</tr>;
        })}</tbody>
      </table>;
    }

    function block(node:MdNode):ReactNode{
      switch(node.name){
        case 'ATXHeading1':case 'SetextHeading1':{const [from,to]=contentRange(node);return <h1 key={key()}>{range(node,from,to)}</h1>}
        case 'ATXHeading2':case 'SetextHeading2':{const [from,to]=contentRange(node);return <h2 key={key()}>{range(node,from,to)}</h2>}
        case 'ATXHeading3':{const [from,to]=contentRange(node);return <h3 key={key()}>{range(node,from,to)}</h3>}
        case 'ATXHeading4':{const [from,to]=contentRange(node);return <h4 key={key()}>{range(node,from,to)}</h4>}
        case 'ATXHeading5':{const [from,to]=contentRange(node);return <h5 key={key()}>{range(node,from,to)}</h5>}
        case 'ATXHeading6':{const [from,to]=contentRange(node);return <h6 key={key()}>{range(node,from,to)}</h6>}
        case 'Paragraph':return <p key={key()}>{range(node,node.from,node.to)}</p>;
        case 'Blockquote':return <blockquote key={key()}>{blocks(node).map(item=>block(item))}</blockquote>;
        case 'BulletList':return <ul key={key()}>{blocks(node).map(item=>block(item))}</ul>;
        case 'OrderedList':{
          const mark=childNamed(node,'ListMark');
          const start=mark?Number.parseInt(slice(text,mark),10):NaN;
          return <ol key={key()} start={Number.isFinite(start)&&start!==1?start:undefined}>{blocks(node).map(item=>block(item))}</ol>;
        }
        case 'HorizontalRule':return <hr key={key()}/>;
        case 'Table':return table(node);
        case 'FencedCode':case 'CodeBlock':{
          const marks=kids(node).filter(item=>item.name==='CodeMark');
          let from=node.from;
          let to=node.to;
          if(marks.length>=2){from=marks[0].to;to=marks[marks.length-1].from}
          else if(marks.length===1)from=marks[0].to;
          const info=childNamed(node,'CodeInfo');
          const language=info?slice(text,info).trim():'';
          const code=text.slice(from,to).replace(/^\r?\n/,'').replace(/\r?\n$/,'');
          return <pre key={key()}><code className={language?`language-${language}`:undefined}>{code}</code></pre>;
        }
        default:
          if(node.firstChild)return <p key={key()}>{range(node,node.from,node.to)}</p>;
          return null;
      }
    }

    function blocks(parent:MdNode):MdNode[]{return kids(parent)}

    const tree=MD_PARSER.parse(text) as unknown as {topNode:MdNode};
    const output=blocks(tree.topNode).map(node=>block(node));
    return output;
  },[text,base]);

  return <>{rendered}</>;
}

/** YAML front matter is common in this corpus; show it rather than dumping it
 *  into the first paragraph (or worse, into an <h2> because of a `---` line). */
export function splitFrontMatter(text:string):{front:string|null;body:string}{
  if(!text.startsWith('---'))return {front:null,body:text};
  const lines=text.split('\n');
  for(let index=1;index<Math.min(lines.length,60);index+=1){
    if(lines[index].trim()==='---'||lines[index].trim()==='...'){
      return {front:lines.slice(0,index+1).join('\n'),body:lines.slice(index+1).join('\n')};
    }
  }
  return {front:null,body:text};
}
