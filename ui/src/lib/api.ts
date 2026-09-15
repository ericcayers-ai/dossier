export type FileNode={rel:string;name?:string;kind?:string;ext?:string;size?:number;mtime?:string;mtime_ns?:number;directory?:boolean;children?:FileNode[]};
export type FileStamp={mtime_ns:number;sha256:string;size:number};
export type Member={rel:string;role:string;size?:number;mtime_ns?:number;stale?:boolean};
export type Bundle={stem_key?:string;members?:Member[];stale?:string[]};
export type Audit={generated_on:string;checks:Array<{id:string;label:string;status:string;detail:string}>;counts:Record<string,number>;status_counts:Record<string,number>;stale:string[];source_status:Record<string,{status:string;policy:string;manual_request:boolean;detail:string}>;manual_sources:string[]};

const tokenKey='dossier-token';
const queryToken=new URLSearchParams(window.location.search).get('token');
if(queryToken)sessionStorage.setItem(tokenKey,queryToken);
const token=()=>sessionStorage.getItem(tokenKey)||'';
const authHeaders=():HeadersInit=>token()?{Authorization:`Bearer ${token()}`}:{};
const withToken=(url:string)=>{const value=token();if(!value)return url;return `${url}${url.includes('?')?'&':'?'}token=${encodeURIComponent(value)}`};
const request=async<T>(url:string,init:RequestInit={}):Promise<T>=>{const headers=new Headers(init.headers);Object.entries(authHeaders()).forEach(([key,value])=>headers.set(key,String(value)));const response=await fetch(url,{...init,headers});if(!response.ok)throw new Error(`${response.status} ${response.statusText}`);return response.json()};
export const api={
 tree:()=>request<FileNode[]>('/api/tree?dir='),
 file:(rel:string)=>request<{content:string;stamp:FileStamp}>(`/api/file?rel=${encodeURIComponent(rel)}`),
 save:(rel:string,content:string,expect?:FileStamp)=>request<{stamp:FileStamp}>('/api/file',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({rel,content,expect})}),
 bundle:(rel:string)=>request<Bundle>(`/api/bundle?rel=${encodeURIComponent(rel)}`),
 search:(query:string)=>request<Array<{rel:string;snippet?:string;kind?:string}>>(`/api/search?q=${encodeURIComponent(query)}`),
 raw:(rel:string)=>withToken(`/api/raw?rel=${encodeURIComponent(rel)}`),
 render:(rel:string)=>withToken(`/api/render?rel=${encodeURIComponent(rel)}`),
 actions:()=>request<Array<{id:string;label:string;applies_to:string[];confirm:boolean;writes:boolean}>>('/api/actions'),
 runAction:(id:string,rel:string,confirmed=false)=>request<{returncode:number;stdout:string;stderr:string}>('/api/actions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id,rel,confirmed})}),
 jobs:()=>request<any[]>('/api/jobs'),
 history:()=>request<any[]>('/api/jobs/history'),
 due:()=>request<any[]>('/api/jobs/due'),
 audit:()=>request<Audit>('/api/audit'),
 handoff:()=>request<{packet:Record<string,unknown>;prompt:string}>('/api/ai/handoff'),
};
