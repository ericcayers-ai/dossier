/** RFC 4180 CSV. Quotes protect delimiters and newlines; `""` is a literal quote.
 *  A contained delimiter must not shift every later column, which is what the
 *  previous `split(',')` did. */

const CANDIDATES=[',',';','\t','|'];

export function sniffDelimiter(text:string):string{
  const firstLine=text.split(/\r?\n/,1)[0]||'';
  let best=CANDIDATES[0];
  let bestCount=-1;
  for(const candidate of CANDIDATES){
    let count=0;
    let quoted=false;
    for(let index=0;index<firstLine.length;index++){
      const character=firstLine[index];
      if(character==='"')quoted=!quoted;
      else if(character===candidate&&!quoted)count+=1;
    }
    if(count>bestCount){bestCount=count;best=candidate}
  }
  return best;
}

export function parseCsv(text:string,delimiter?:string):string[][]{
  const separator=delimiter??sniffDelimiter(text);
  const rows:string[][]=[];
  let row:string[]=[];
  let field='';
  let quoted=false;
  let index=0;
  const push=()=>{row.push(field);field=''};
  const endRow=()=>{push();rows.push(row);row=[]};
  while(index<text.length){
    const character=text[index];
    if(quoted){
      if(character==='"'){
        if(text[index+1]==='"'){field+='"';index+=2;continue}
        quoted=false;index+=1;continue;
      }
      field+=character;index+=1;continue;
    }
    if(character==='"'){quoted=true;index+=1;continue}
    if(character===separator){push();index+=1;continue}
    if(character==='\n'){endRow();index+=1;continue}
    if(character==='\r'){if(text[index+1]==='\n')index+=1;endRow();index+=1;continue}
    field+=character;index+=1;
  }
  if(field.length>0||row.length>0)endRow();
  // A single trailing newline should not invent an empty row.
  while(rows.length>0&&rows[rows.length-1].every(cell=>cell===''))rows.pop();
  return rows;
}

export type CsvShape={header:string[];rows:string[][];delimiter:string;width:number;ragged:number};

export function shapeCsv(text:string,delimiter?:string):CsvShape{
  const grid=parseCsv(text,delimiter);
  const header=grid.shift()??[];
  const width=header.length;
  const ragged=grid.filter(row=>row.length!==width).length;
  return {header,rows:grid,delimiter:delimiter??sniffDelimiter(text),width,ragged};
}
