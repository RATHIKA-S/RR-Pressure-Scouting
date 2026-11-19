"use strict";
const main = document.querySelector("main");
const disciplines = ["Batters", "Bowlers"];
const state = {role:"Batters", filters:{}, comparison:[]};
const dimensions = [["Competition",1,["IPL","T20I"]],["Season",2,["2022","2023","2024","2025","2026"]],["Phase",3,["Powerplay","Middle","Death"]],["Innings",4,["1","2"]]];
const escapeText = value => String(value).replace(/[&<>"']/g, c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const fmt = v => Number(v).toLocaleString("en-US");
const signed = v => (v>0?"+":"")+v;
const route = (role,id) => "#player/"+role+"/"+id;
function mast(title,desc){return '<section class="mast"><div class="kicker">SupeRR Selector · IPL 2027 auction</div><h1>'+escapeText(title)+'</h1><p>'+desc+'</p></section>';}
function stats(items){return '<div class="stats">'+items.map(([label,value])=>'<div class="stat"><strong>'+value+'</strong><span>'+label+'</span></div>').join("")+'</div>';}
function table(head,rows){return '<div class="scroll" tabindex="0"><table><thead><tr>'+head.map(x=>'<th scope="col">'+x+'</th>').join("")+'</tr></thead><tbody>'+rows.map(row=>'<tr>'+row.map(cell=>'<td>'+cell+'</td>').join("")+'</tr>').join("")+'</tbody></table></div>';}
function playerLink(role,r){return '<a href="'+route(role,r.id)+'">'+escapeText(r.name)+'</a>';}
function roleButtons(){return '<div class="actions">'+disciplines.map(x=>'<button data-role="'+x+'" aria-pressed="'+(state.role===x)+'" class="'+(state.role===x?'selected':'')+'">'+x+'</button>').join("")+'</div>';}
function filters(){return '<div class="controls">'+dimensions.map(([name,i,opts])=>'<label>'+name+'<select data-filter="'+i+'"><option value="">All</option>'+opts.map(x=>'<option '+(state.filters[i]===x?'selected':'')+'>'+x+'</option>').join("")+'</select></label>').join("")+'<button data-reset>Reset filters</button></div>';}
function split(role){
    const summary=new Map();
    for(const row of DATA.segments[role]){
        if(dimensions.some(([,i])=>state.filters[i] && String(row[i])!==state.filters[i]))continue;
        if(!summary.has(row[0]))summary.set(row[0],[[0,0,0],[0,0,0]]);
        const bucket=summary.get(row[0])[row[5]];
        for(let i=0;i<3;i++)bucket[i]+=row[6+i];
    }
    return summary;
}
function csv(role){
    const fields=["rank","name","rating","balls","matches","win","lift","phase"];
    const records=DATA.roles[role].slice(0,10).map(r=>fields.map(f=>'"'+String(r[f]).replaceAll('"','""')+'"').join(','));
    const url=URL.createObjectURL(new Blob([[fields.join(','),...records].join('\r\n')],{type:"text/csv"}));
    const a=document.createElement("a");a.href=url;a.download=role.toLowerCase()+".csv";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
function overview(){
    const cards=disciplines.map(role=>'<section class="card feature"><div class="tag">Submission shortlist</div><h2>Top '+role.toLowerCase()+'</h2>'+DATA.roles[role].slice(0,3).map(r=>'<div class="row"><div><span class="rank">'+r.rank+'</span>'+playerLink(role,r)+'</div><span>'+r.rating.toFixed(2)+' <small>/ 100</small></span></div>').join("")+'<a class="btn" href="#rankings/'+role+'">View top 10 →</a></section>');
    return mast("Pressure scouting","Who delivers when the game gets tight? Explore the IPL and T20I evidence behind each auction shortlist.")+stats([["Matches analysed",fmt(DATA.audit["Analysed matches"])],["Deliveries analysed",fmt(DATA.audit["Analysed rows"])],["Eligible batters",DATA.roles.Batters.length],["Eligible bowlers",DATA.roles.Bowlers.length]])+'<div class="grid">'+cards.join("")+'</div><p class="note"><b>Reading the rating.</b> Half the score rewards performance against comparable peers, 30% rewards lift above the player’s own baseline, and 20% rewards consistency across matches. <a href="#method">Inspect the model →</a></p>';
}
function rankings(){
    const role=state.role, ranks=DATA.roles[role], exploring=Object.values(state.filters).some(Boolean);
    const header=mast("Player rankings","The submission lists use the full eligible pool. Apply filters to inspect the evidence underneath those ranks.")+roleButtons()+filters();
    if(exploring){
        const groups=split(role);
        const rows=ranks.filter(r=>groups.get(r.id)?.[1][0]>0).map(r=>{
            const [o,p]=groups.get(r.id);
            return [r.rank,playerLink(role,r),p[0],rate(role,p),rate(role,o),p[2],p[0]<30?'Thin sample':'Available'];
        });
        return header+'<h2>Filtered performance</h2><p>Rows retain their full-data rank. Rates are raw within the selected context. Samples below 30 pressure balls are flagged.</p>'+(rows.length?table(["Full rank","Player","Pressure balls","Pressure rate","Ordinary rate","Dismissals / wickets","Evidence"],rows):'<p>No eligible players faced pressure in this selection.</p>')+'<p>'+unit(role)+'</p>';
    }
    const rows=ranks.map(r=>[r.rank,playerLink(role,r),r.rating.toFixed(2),signed(r.lift),r.matches,r.win+'%',r.balls]);
    return header+'<div class="row"><h2>Official top 10</h2><button data-csv="'+role+'">Download top 10 CSV</button></div>'+table(["Rank","Player","Rating","Lift / 100","Matches ≥3 balls","Above baseline","Pressure balls"],rows.slice(0,10))+'<details><summary>Full eligible field · '+rows.length+' players</summary>'+table(["Rank","Player","Rating","Lift / 100","Matches ≥3 balls","Above baseline","Pressure balls"],rows)+'</details>';
}
function unit(role){return role==="Batters"?"Batting rate is runs per 100 balls faced.":"Bowling rate is charged runs per six legal balls.";}
function rate(role,bucket){return bucket?.[0]?(bucket[1]*(role==='Batters'?100:6)/bucket[0]).toFixed(2):'—';}
function chart(history){
    const w=660,h=135,pad=24;
    const bound=Math.max(10,...history.map(x=>Math.abs(x[2])));
    const points=history.map(([id,balls,lift],i)=>{
        const x=pad+(w-2*pad)*i/Math.max(history.length-1,1),y=h/2-lift/bound*(h/2-10);
        return '<circle cx="'+x+'" cy="'+y+'" r="4.2" fill="'+(lift>=0?'#a8255b':'#304b70')+'"><title>'+escapeText(DATA.matches[id].join(' · '))+' / '+balls+' balls / lift '+signed(lift)+'</title></circle>';
    });
    return '<svg role="img" aria-label="Match lift by date, horizontal line is the personal baseline" class="plot" viewBox="0 0 '+w+' '+h+'"><line x1="12" x2="648" y1="67.5" y2="67.5" stroke="#8792a2" stroke-dasharray="5 4"/>'+points.join('')+'</svg>';
}
function player(role,id){
    const r=DATA.roles[role]?.find(x=>x.id===Number(id));
    if(!r)return mast("Player unavailable",'<a href="#rankings">Return to rankings</a>');
    const [o,p]=splitWithoutFilters(role,id);
    const history=[...r.history].sort((a,b)=>DATA.matches[a[0]][0].localeCompare(DATA.matches[b[0]][0]));
    const years=Object.keys(r).filter(k=>k.startsWith("omit")).sort();
    const evidence=history.map(([mid,balls,lift,situation])=>[escapeText(DATA.matches[mid][0]),escapeText(DATA.matches[mid].slice(1).join(' v ')),escapeText(situation),balls,signed(lift)]);
    return mast(r.name,'<a href="#rankings/'+role+'">'+role+'</a> / Rank '+r.rank+' · '+escapeText(r.phase)+' overs')+
        '<p class="note"><b>RR role fit.</b> Assess for '+r.phase.toLowerCase()+'-overs '+(role==="Batters"?'batting':'bowling')+', the phase with the most pressure balls for this player. Across all phases, '+r.win+'% of qualifying matches exceeded the personal baseline. Auction availability is unverified.</p>'+
        stats([["Rating / 100",r.rating.toFixed(2)],["Pressure balls",fmt(r.balls)],["Qualifying matches",r.matches],["Adjusted lift / 100",signed(r.lift)]])+
        '<div class="grid"><section class="card"><h2>Pressure vs ordinary</h2>'+table(["Situation","Balls","Rate","Dismissals / wickets"],[["Pressure",p[0],rate(role,p),p[2]],["Ordinary",o[0],rate(role,o),o[2]]])+'<small>'+unit(role)+' Rates here are unadjusted.</small></section><section class="card"><h2>How stable is the result?</h2><p>90% interval for adjusted lift per 100 balls <b>'+signed(r.ci[0])+' to '+signed(r.ci[1])+'</b>.</p><p>IPL-only rank <b>'+ (r.ipl??'Ineligible')+'</b> · Tighter pressure rule <b>'+(r.strict??'Ineligible')+'</b></p><details><summary>Leave one season out</summary>'+years.map(k=>'<div>Without '+k.slice(4)+' · '+(r[k]??'Ineligible')+'</div>').join("")+'</details></section></div>'+
        '<section class="card"><h2>Match-by-match lift</h2><p>Each dot is one match with at least three pressure balls. Above the line means better than the context-matched personal baseline. Time runs left to right.</p>'+chart(history)+'<details><summary>View all '+history.length+' match observations</summary>'+table(["Date","Match","First pressure event","Pressure balls","Lift / 100"],evidence)+'</details></section>';
}
function splitWithoutFilters(role,id){
    const out=[[0,0,0],[0,0,0]];
    for(const row of DATA.segments[role])if(row[0]===Number(id))for(let i=0;i<3;i++)out[row[5]][i]+=row[6+i];
    return out;
}
function compare(){
    const role=state.role, ranks=DATA.roles[role];
    const pair=[0,1].map(i=>ranks.find(r=>r.id===Number(state.comparison[i]))||ranks[i]);
    const pickers=pair.map((r,i)=>'<label>Player '+(i+1)+'<select data-picker="'+i+'">'+ranks.map(n=>'<option value="'+n.id+'" '+(r.id===n.id?'selected':'')+'>'+escapeText(n.name)+'</option>').join("")+'</select></label>');
    const start=mast('Compare players','Select two players in the same discipline and compare their performance in the same match context.')+roleButtons()+'<div class="controls">'+pickers.join('')+'</div>'+filters();
    if(pair[0].id===pair[1].id)return start+'<p class="note">Select two different players to compare.</p>';
    const g=split(role), samples=pair.map(r=>g.get(r.id)||[[0,0,0],[0,0,0]]);
    const rows=[["Official rank",...pair.map(r=>r.rank)],["Official rating",...pair.map(r=>r.rating.toFixed(2))],["Pressure balls",...samples.map(x=>x[1][0])],["Pressure rate",...samples.map(x=>rate(role,x[1]))],["Ordinary rate",...samples.map(x=>rate(role,x[0]))],["Pressure dismissals / wickets",...samples.map(x=>x[1][2])],["Full-data lift interval",...pair.map(r=>r.ci.map(signed).join(' to '))]];
    const stronger=(Number(rate(role,samples[0][1]))-Number(rate(role,samples[1][1])))*(role==='Batters'?1:-1);
    const note=samples.some(x=>x[1][0]<30)?"Insufficient evidence for a filtered verdict. At least one player has fewer than 30 pressure balls.":stronger===0?"Both players have the same pressure scoring rate to two decimals.":escapeText(pair[stronger>0?0:1].name)+(role==='Batters'?' scores faster':' concedes fewer runs per over')+' under pressure in this selection. Compare wickets and exposure alongside the rate.';
    return start+table(["Measure",...pair.map(r=>playerLink(role,r))],rows)+'<p>'+unit(role)+'</p><p class="note">'+note+'</p>';
}
function method(){
    return mast('Methodology','Reproduce the pressure definition, inspect exclusions, and download the submission evidence.')+'<div class="actions"><a class="btn primary" download="methodology.pdf" href="data:application/pdf;base64,'+DATA.pdf+'">Download methodology PDF</a>'+disciplines.map(role=>'<button data-csv="'+role+'">'+role+' CSV</button>').join('')+'</div><div class="grid"><section class="card"><h2>Rating model</h2>'+DATA.method.map(([h,t])=>'<details><summary>'+escapeText(h)+'</summary><p>'+escapeText(t)+'</p></details>').join('')+'</section><section class="card"><h2>Coverage audit</h2>'+table(["Measure","Count"],Object.entries(DATA.audit).map(([k,v])=>[k,typeof v==="number"?fmt(v):escapeText(v)]))+'</section></div><section class="card"><h2>Worked deliveries</h2>'+Object.entries(DATA.examples).map(([k,v])=>'<h3>'+k+'</h3><p>'+escapeText(v)+'</p>').join('')+'</section>';
}
function render(){
    const [page="overview",role,id]=location.hash.slice(1).split('/');
    if(disciplines.includes(role))state.role=role;
    const tabs=[["overview","Overview"],["rankings","Rankings"],["compare","Compare"],["method","Methodology"]];
    document.querySelector("nav").innerHTML=tabs.map(([key,text])=>'<a href="#'+key+'" class="'+((page||"overview")===key?'active':'')+'">'+text+'</a>').join("");
    main.innerHTML=page==="rankings"?rankings():page==="player"?player(role,id):page==="compare"?compare():page==="method"?method():overview();
}
main.addEventListener('click',e=>{
    const b=e.target.closest('button');if(!b)return;
    if(b.dataset.csv){csv(b.dataset.csv);return;}
    if(b.hasAttribute('data-reset'))state.filters={};
    if(b.dataset.role){state.role=b.dataset.role;state.comparison=[];history.replaceState(null,'',location.hash.split('/')[0]+'/'+state.role);}
    render();
});
main.addEventListener('change',e=>{
    const t=e.target;
    if(t.dataset.filter!==undefined)state.filters[t.dataset.filter]=t.value;
    if(t.dataset.picker!==undefined)state.comparison[t.dataset.picker]=t.value;
    render();
    const attr=t.dataset.filter!==undefined?'filter':'picker';
    main.querySelector('[data-'+attr+'="'+t.dataset[attr]+'"]')?.focus();
});
window.addEventListener('hashchange',()=>{state.filters={};render();window.scrollTo(0,0);});
render();
