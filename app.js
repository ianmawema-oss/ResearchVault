const $ = id => document.getElementById(id);
function esc(s){return String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));}
function authors(a){return (a||[]).slice(0,5).join(", ")+(a?.length>5?" et al.":"");}
async function search(){
 const q=$("query").value.trim(); if(q.length<3){$("status").textContent="Enter at least three characters.";return;}
 $("searchBtn").disabled=true;$("status").textContent="Searching scholarly sources…";$("results").innerHTML="";$("count").textContent="";
 const params=new URLSearchParams({q,limit:"25"});if($("fromYear").value)params.set("from_year",$("fromYear").value);if($("toYear").value)params.set("to_year",$("toYear").value);
 try{
  const r=await fetch("/api/search?"+params);const data=await r.json();if(!r.ok)throw new Error(data.detail||"Search failed");
  $("resultTitle").textContent="Results for “"+q+"”";$("count").textContent=data.count+" records";
  $("status").textContent=data.count?data.notice:"No records returned. Try broader keywords or remove filters.";
  $("results").innerHTML=data.results.map((p,i)=>`<article class="paper">
   <div class="tags"><span class="tag">${esc(p.source||"Scholarly source")}</span><span class="tag green">Metadata record found</span>${p.open_access_url?'<span class="tag green">Open-access link found</span>':''}</div>
   <h3>${esc(p.title)}</h3><div class="meta">${esc(authors(p.authors))} · ${esc(p.year||"Year unavailable")} · ${esc(p.journal||"Journal unavailable")}</div>
   ${p.abstract?`<p class="abstract">${esc(p.abstract.slice(0,650))}${p.abstract.length>650?"…":""}</p>`:""}
   <div class="meta">${p.doi?"DOI: "+esc(p.doi):"DOI not supplied by this source"}</div>
   <div class="actions">${p.url?`<a href="${esc(p.url)}" target="_blank" rel="noopener">Publication record ↗</a>`:""}${p.open_access_url?`<a href="${esc(p.open_access_url)}" target="_blank" rel="noopener">Full-text location ↗</a>`:""}${p.doi?`<button onclick="verifyDoi('${esc(p.doi)}')">Verify DOI</button>`:""}<button class="save" onclick='savePaper(${JSON.stringify(p).replace(/'/g,"&#39;")})'>Save to library</button></div>
  </article>`).join("");
  if(data.source_errors?.length)$("status").textContent+=" Some sources did not respond: "+data.source_errors.map(e=>e.source).join(", ")+".";
 }catch(e){$("status").textContent="Search error: "+e.message;}finally{$("searchBtn").disabled=false;}
}
async function verifyDoi(doi){
 try{const r=await fetch("/api/verify?doi="+encodeURIComponent(doi));const d=await r.json();alert(r.ok?`${d.status}\n${d.title||d.message||""}\n${d.limitation||""}`:(d.detail||"Verification failed"));}catch(e){alert(e.message)}
}
async function savePaper(p){
 const r=await fetch("/api/saved",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(p)});
 if(r.ok){$("status").textContent="Publication saved to your local library.";loadSaved();}else alert("Could not save publication.");
}
async function loadSaved(){
 const r=await fetch("/api/saved");const data=await r.json();
 $("savedList").innerHTML=data.length?data.map(p=>`<div class="saveditem"><span><strong>${esc(p.title)}</strong><br><span class="muted">${esc(p.doi||"No DOI")} · ${esc(p.year||"")}</span></span><button class="ghost" onclick="deleteSaved(${p.id})">Remove</button></div>`).join(""):'<p class="muted">No saved papers yet. Search and save publications to build your library.</p>';
}
async function deleteSaved(id){await fetch("/api/saved/"+id,{method:"DELETE"});loadSaved();}
$("searchBtn").addEventListener("click",search);$("query").addEventListener("keydown",e=>{if(e.key==="Enter")search()});$("refreshSaved").addEventListener("click",loadSaved);
loadSaved();
