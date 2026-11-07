import {useMemo,useState} from 'react';
import {shapeCsv} from '../lib/csv';
import {count,isOne} from '../lib/copy';

/** The real CSV grid. RFC 4180 parsing (quoted fields, embedded delimiters and
 *  newlines), delimiter sniffing, a sticky header, click-to-sort with numeric
 *  detection, and mono + tabular-nums as DESIGN.md:68 specifies.
 *  This file was a 32-byte `export {default} from '../App'` shim with no
 *  importer; the grid now lives where its name says it does. */
export default function CsvGrid({text,delimiter}:{text:string;delimiter?:string}){
  const shape=useMemo(()=>shapeCsv(text,delimiter),[text,delimiter]);
  const [sort,setSort]=useState<{column:number;direction:1|-1}|null>(null);

  const rows=useMemo(()=>{
    if(!sort)return shape.rows;
    const copy=[...shape.rows];
    copy.sort((left,right)=>{
      const a=(left[sort.column]??'').trim();
      const b=(right[sort.column]??'').trim();
      const numeric=/^-?[\d.,$%]+$/.test(a)&&/^-?[\d.,$%]+$/.test(b);
      if(numeric){
        const na=Number(a.replace(/[$,%]/g,''));
        const nb=Number(b.replace(/[$,%]/g,''));
        if(Number.isFinite(na)&&Number.isFinite(nb))return (na-nb)*sort.direction;
      }
      return a.localeCompare(b,undefined,{numeric:true,sensitivity:'base'})*sort.direction;
    });
    return copy;
  },[shape.rows,sort]);

  if(shape.header.length===0)return <div className="empty">This CSV has no rows.</div>;

  const toggle=(column:number)=>setSort(current=>current&&current.column===column?{column,direction:current.direction===-1?1:-1}:{column,direction:1});

  return <div className="table-wrap">
    <table className="data-table mono-table">
      <caption className="sr-only">{`${shape.rows.length} rows, ${shape.width} columns, delimiter ${shape.delimiter==='\t'?'tab':`"${shape.delimiter}"`}`}</caption>
      <thead><tr>{shape.header.map((cell,column)=><th key={column} aria-sort={sort?.column===column?(sort.direction===1?'ascending':'descending'):'none'}>
        <button type="button" onClick={()=>toggle(column)} title={`Sort by ${cell||`column ${column+1}`}`}>
          {cell||`column ${column+1}`}{sort?.column===column?(sort.direction===1?' ↑':' ↓'):''}
        </button>
      </th>)}</tr></thead>
      <tbody>{rows.map((row,index)=><tr key={index}>{shape.header.map((_,column)=><td key={column} title={row[column]||''}>{row[column]||''}</td>)}</tr>)}</tbody>
    </table>
    {shape.ragged>0&&<p className="csv-note">{count(shape.ragged,'row')} {isOne(shape.ragged)?'does':'do'} not have {shape.width} fields. The first is probably a bad quote or an unescaped newline.</p>}
  </div>;
}
