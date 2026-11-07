export type FileNode={rel:string;name?:string;kind?:string;ext?:string;size?:number;mtime?:string;mtime_ns?:number;directory?:boolean;children?:FileNode[]};

export const IMAGE_EXTS=['png','jpg','jpeg','gif','webp','svg','bmp','avif'];
export const BINARY_EXTS=['pdf','docx','doc','xlsx','xls','pptx','zip','gz','7z','exe','dll','woff','woff2','ttf','mp3','mp4'];

export const extOf=(rel:string)=>rel.split('.').pop()?.toLowerCase()||'';
export const baseName=(rel:string)=>rel.split('/').pop()||rel;
export const dirOf=(rel:string)=>{const index=rel.lastIndexOf('/');return index<0?'':rel.slice(0,index+1)};
export const nameOf=(node:FileNode)=>node.name||baseName(node.rel);
export const isImage=(rel:string)=>IMAGE_EXTS.includes(extOf(rel));
export const isBinary=(rel:string)=>IMAGE_EXTS.includes(extOf(rel))||BINARY_EXTS.includes(extOf(rel));
export const icon=(rel:string)=>({md:'M',json:'{}',py:'Py',csv:'▦',pdf:'▤',docx:'W',svg:'◈',png:'◈',jpg:'◈',jpeg:'◈',gif:'◈',webp:'◈',txt:'T'}[extOf(rel)]||'·');

export function flatten(nodes:FileNode[]):FileNode[]{
  return nodes.flatMap(node=>node.children?.length?flatten(node.children):[node]).filter(node=>!node.directory&&!node.children);
}
export function formatBytes(size?:number):string{
  if(typeof size!=='number')return '';
  if(size<1024)return `${size} B`;
  if(size<1024*1024)return `${Math.round(size/1024)} KB`;
  return `${(size/1024/1024).toFixed(1)} MB`;
}
/** A timestamp a person reads: the clock for today, the date and clock before that.
 *  The trash listed `2026-11-05T14:14:51.525417+00:00` for every copy, which is a
 *  machine field, not a time. */
export function formatWhen(iso?:string|null):string{
  if(!iso)return '';
  const date=new Date(iso);
  if(Number.isNaN(date.getTime()))return iso;
  const pad=(n:number)=>String(n).padStart(2,'0');
  const clock=`${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
  if(date.toDateString()===new Date().toDateString())return clock;
  return `${date.getDate()} ${date.toLocaleString('en',{month:'short'})} ${clock}`;
}
export function formatAge(mtimeNs?:number):string{
  if(typeof mtimeNs!=='number')return '';
  const seconds=Math.max(0,(Date.now()-mtimeNs/1e6)/1000);
  if(seconds<60)return 'just now';
  if(seconds<3600)return `${Math.floor(seconds/60)}m ago`;
  if(seconds<86400)return `${Math.floor(seconds/3600)}h ago`;
  return `${Math.floor(seconds/86400)}d ago`;
}
/** Does a declared `applies_to` pattern match this path? `*.docx` / `resume*` / exact. */
export function matchesPattern(rel:string,pattern:string):boolean{
  const name=baseName(rel);
  const target=pattern.includes('/')?rel:name;
  if(pattern==='*'||pattern==='')return true;
  const escaped=pattern.replace(/[.+^${}()|[\]\\]/g,'\\$&').replace(/\*/g,'.*').replace(/\?/g,'.');
  return new RegExp(`^${escaped}$`,'i').test(target);
}
export function appliesTo(rel:string,patterns?:string[]):boolean{
  if(!patterns||patterns.length===0)return false;
  return patterns.some(pattern=>matchesPattern(rel,pattern));
}
/** Sibling path for an export target: `a/b.docx` -> `a/b.pdf`. */
export function siblingWith(rel:string,extension:string):string{
  const index=rel.lastIndexOf('.');
  return `${index<0?rel:rel.slice(0,index)}.${extension.replace(/^\./,'')}`;
}
