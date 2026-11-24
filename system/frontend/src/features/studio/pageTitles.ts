export function updatedPageTitles(titles:Record<string,string>,language:'en'|'ar',value:string):Record<string,string>{
 const title=value.trim();
 if(!title||title.length>120)throw Error('Use a title between 1 and 120 characters.');
 return {...titles,[language]:title};
}
export function pageTitlesKey(titles:Record<string,string>):string{return JSON.stringify(Object.keys(titles).sort().map(k=>[k,titles[k]]));}
