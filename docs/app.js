const DATA_URL = "data/opportunities.json";
const STATE_KEY = "fundedICTOpportunityWatchState.v1";
const THEME_KEY = "fundedICTOpportunityWatchTheme";
let records = [];

const $ = (s, root=document) => root.querySelector(s);
const $$ = (s, root=document) => [...root.querySelectorAll(s)];
const state = JSON.parse(localStorage.getItem(STATE_KEY) || "{}");

function saveState(){ localStorage.setItem(STATE_KEY, JSON.stringify(state)); updateStats(); }
function keyFor(r){ return (r.canonical_url || `${r.host}|${r.title}|${r.cycle}`).toLowerCase().replace(/[?#].*$/,").replace(/\/$/,"); }
function personal(r){ const k=keyFor(r); return state[k] || (state[k]={applied:false,interested:false,ignored:false,notes:""}); }

function extractDates(r){
  const raw = [r.deadline, ...(r.deadlines||[])].filter(Boolean).join(" ");
  const matches = raw.match(/\d{4}-\d{2}-\d{2}(?:T[^\s;,]+)?/g) || [];
  return matches.map(x => {
    const d = new Date(x.length===10 ? `${x}T23:59:59` : x);
    return isNaN(d) ? null : d;
  }).filter(Boolean);
}
function statusFor(r){
  const text = String(r.deadline||"").toLowerCase();
  if(/rolling|permanently open|no fixed deadline/.test(text)) return "ROLLING";
  const now = new Date();
  const dates = extractDates(r).sort((a,b)=>a-b);
  if(!dates.length) return "OPEN";
  const future = dates.find(d => d >= now);
  if(!future) return "CLOSED";
  const days = (future-now)/86400000;
  return days <= 7 ? "CLOSING SOON" : "OPEN";
}
function deadlineSortValue(r){
  const now = new Date();
  const future = extractDates(r).sort((a,b)=>a-b).find(d=>d>=now);
  if(future) return future.getTime();
  if(statusFor(r)==="ROLLING") return Number.MAX_SAFE_INTEGER-1;
  return Number.MAX_SAFE_INTEGER;
}
function categoryFor(r){
  const t = [r.title,r.host,r.program_family,r.cycle,r.funding_stream,r.location_format].filter(Boolean).join(" ").toLowerCase();
  if(/cyber|security|privacy|trust|threat|malware|phishing|secure/.test(t)) return "Cybersecurity";
  if(/\b6g\b|\b5g\b|b5g|wireless|network|radiocommunication|telecom|mobicom|slicing/.test(t)) return "Networks";
  if(/policy|governance|humanism|nato|internet freedom|information controls/.test(t)) return "Policy";
  if(/\bai\b|artificial intelligence|machine learning|alignment|mats|lasr|agentic|model/.test(t)) return "AI";
  return "Funding";
}
function titleFor(r){ return r.title || r.program_family || "Opportunity"; }
function displayDeadline(r){ return (r.deadlines||[]).length ? r.deadlines.join(" · ") : (r.deadline || "Check official call"); }
function displayFunding(r){ return r.funding || r.funding_stream || "See official call"; }
function displayDates(r){ return r.programme_dates || "See official call"; }
function displayLocation(r){ return r.location_format || r.location_or_format || "See official call"; }
function displayAliases(r){
  const a=[...(r.aliases||[])];
  if(r.covered_cohorts?.length) a.push(`Cohorts: ${r.covered_cohorts.join(", ")}`);
  return a.join(" · ") || "—";
}
function prettyStatusClass(s){ return s==="OPEN"?"open":s==="CLOSING SOON"?"soon":s==="ROLLING"?"rolling":"closed"; }

function render(){
  const q=$("#searchInput").value.trim().toLowerCase();
  const sf=$("#statusFilter").value;
  const cf=$("#categoryFilter").value;
  const hideIgnored=$("#hideIgnored").checked;
  const sort=$("#sortFilter").value;

  let items = records.filter(r=>{
    const p=personal(r), status=statusFor(r), cat=categoryFor(r);
    if(hideIgnored && p.ignored) return false;
    if(sf==="active" && status==="CLOSED") return false;
    if(sf!=="active" && sf!=="all" && status!==sf) return false;
    if(cf!=="all" && cat!==cf) return false;
    if(q){
      const hay=[r.title,r.host,r.program_family,r.cycle,r.deadline,r.funding,r.funding_stream,r.location_format,...(r.aliases||[])].filter(Boolean).join(" ").toLowerCase();
      if(!hay.includes(q)) return false;
    }
    return true;
  });

  items.sort((a,b)=>{
    if(sort==="newest") return String(b.reported_at||"").localeCompare(String(a.reported_at||""));
    if(sort==="title") return titleFor(a).localeCompare(titleFor(b));
    return deadlineSortValue(a)-deadlineSortValue(b);
  });

  const cards=$("#cards"); cards.innerHTML="";
  const tpl=$("#cardTemplate");
  for(const r of items){
    const node=tpl.content.firstElementChild.cloneNode(true);
    const p=personal(r), status=statusFor(r), cat=categoryFor(r);
    $(".status",node).textContent=status; $(".status",node).classList.add(prettyStatusClass(status));
    $(".category",node).textContent=cat;
    $(".title",node).textContent=titleFor(r);
    $(".host",node).textContent=r.host || "";
    $(".deadline",node).textContent=displayDeadline(r);
    $(".dates",node).textContent=displayDates(r);
    $(".location",node).textContent=displayLocation(r);
    $(".funding",node).textContent=displayFunding(r);
    $(".family",node).textContent=r.program_family || "—";
    $(".cycle",node).textContent=r.cycle || "—";
    $(".stream",node).textContent=r.funding_stream || "—";
    $(".aliases",node).textContent=displayAliases(r);
    $(".reported",node).textContent=r.reported_at || "—";

    const official=$(".apply-link",node);
    official.href=r.application_url || r.canonical_url || "#";

    const star=$(".star",node);
    const applied=$(".applied-btn",node);
    const ignore=$(".ignore-btn",node);
    const notes=$(".notes",node);

    if(p.interested){star.textContent="★";star.classList.add("active");node.classList.add("is-interested")}
    if(p.applied){applied.textContent="Applied ✓";applied.classList.add("active");node.classList.add("is-applied")}
    if(p.ignored){ignore.textContent="Unignore"}
    notes.value=p.notes||"";

    star.addEventListener("click",()=>{p.interested=!p.interested;saveState();render()});
    applied.addEventListener("click",()=>{p.applied=!p.applied;saveState();render()});
    ignore.addEventListener("click",()=>{p.ignored=!p.ignored;saveState();render()});
    notes.addEventListener("change",()=>{p.notes=notes.value;saveState()});

    cards.appendChild(node);
  }
  $("#emptyState").hidden=items.length!==0;
  updateStats();
}
function updateStats(){
  const statuses=records.map(statusFor);
  $("#totalCount").textContent=records.length;
  $("#openCount").textContent=statuses.filter(x=>x==="OPEN").length;
  $("#soonCount").textContent=statuses.filter(x=>x==="CLOSING SOON").length;
  $("#rollingCount").textContent=statuses.filter(x=>x==="ROLLING").length;
  $("#appliedCount").textContent=records.filter(r=>personal(r).applied).length;
}
function exportStatus(){
  const payload={exported_at:new Date().toISOString(),state};
  const blob=new Blob([JSON.stringify(payload,null,2)],{type:"application/json"});
  const a=document.createElement("a");a.href=URL.createObjectURL(blob);a.download="funded-ict-watch-my-status.json";a.click();URL.revokeObjectURL(a.href);
}
function setTheme(theme){
  document.documentElement.dataset.theme=theme;
  localStorage.setItem(THEME_KEY,theme);
}
async function init(){
  const savedTheme=localStorage.getItem(THEME_KEY);
  if(savedTheme) setTheme(savedTheme);
  try{
    const res=await fetch(`${DATA_URL}?v=${Date.now()}`,{cache:"no-store"});
    if(!res.ok) throw new Error(`HTTP ${res.status}`);
    const data=await res.json();
    records=data.opportunities||[];
    $("#lastSync").textContent=`Monitor data updated: ${data.updated_at || "unknown"} · ${records.length} tracked records`;
    render();
  }catch(e){
    $("#lastSync").textContent="Could not load dashboard data. Refresh or check the repository data file.";
    console.error(e);
  }
}
["searchInput","statusFilter","categoryFilter","sortFilter","hideIgnored"].forEach(id=>{
  document.addEventListener("input",e=>{if(e.target?.id===id) render()});
  document.addEventListener("change",e=>{if(e.target?.id===id) render()});
});
$("#exportBtn").addEventListener("click",exportStatus);
$("#themeBtn").addEventListener("click",()=>{
  const current=document.documentElement.dataset.theme || (matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light");
  setTheme(current==="dark"?"light":"dark");
});
init();
