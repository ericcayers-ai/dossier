import type {FileStamp} from './api';

/** One open document. `content === undefined` means "there is no editable
 *  buffer for this tab" — a binary file, or a read that failed. A read failure
 *  never becomes the buffer, so ⌘S can never write English prose over a file. */
export type Tab={
  rel:string;
  content?:string;
  stamp?:FileStamp;
  dirty?:boolean;
  loaded?:boolean;
  error?:{title:string;next:string;raw?:string};
  savedAt?:number;
};

const DRAFT_PREFIX='dossier-draft:';
const THEME_KEY='dossier-theme';

/** Drafts are per-tab in sessionStorage: never the source, never across sessions. */
export function writeDraft(rel:string,content:string):void{
  try{sessionStorage.setItem(DRAFT_PREFIX+rel,content)}catch{/* storage full or blocked */}
}
export function readDraft(rel:string):string|null{
  try{return sessionStorage.getItem(DRAFT_PREFIX+rel)}catch{return null}
}
export function clearDraft(rel:string):void{
  try{sessionStorage.removeItem(DRAFT_PREFIX+rel)}catch{/* ignore */}
}

export function readStoredTheme():'light'|'dark'|null{
  try{
    const value=localStorage.getItem(THEME_KEY);
    if(value==='light'||value==='dark')return value;
  }catch{/* ignore */}
  return null;
}
export function storeTheme(theme:'light'|'dark'):void{
  try{localStorage.setItem(THEME_KEY,theme)}catch{/* ignore */}
}
export function preferredTheme():'light'|'dark'{
  const stored=readStoredTheme();
  if(stored)return stored;
  try{if(window.matchMedia('(prefers-color-scheme: dark)').matches)return 'dark'}catch{/* ignore */}
  return 'light';
}

export function clockTime(at?:number):string{
  if(!at)return '';
  const date=new Date(at);
  const pad=(value:number)=>String(value).padStart(2,'0');
  return `${pad(date.getHours())}:${pad(date.getMinutes())}`;
}
