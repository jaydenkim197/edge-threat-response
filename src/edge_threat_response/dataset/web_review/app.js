"use strict";
const $ = id => document.getElementById(id);
const specs = [
  ["domain", "① CCTV형 장면인가요?", "위에서 비스듬히 · 넓은 시야", [["target_cctv","CCTV형"],["non_target","그 외"],["unclear","모르겠음"]]],
  ["annotation_verdict", "② 칼 라벨은 정상인가요?", "박스 위치 + 칼 누락을 한 번에 확인", [["ok","정상"],["problem","문제 있음"],["unclear","모르겠음"]]],
];
let items = [], current = 0, csrf = "", pack = "", values = {}, dirty = false, saving = false, timer;
const teamDataset=location.pathname.startsWith("/review/")?location.pathname.split("/")[2]:"";
const apiUrl=path=>path+(teamDataset?`?dataset=${encodeURIComponent(teamDataset)}`:"");
let team=false, signedReviewer="", teamAdmin=false;
let rememberReviewer = localStorage.getItem("etr-reviewer") || "";
function status(text, kind="") { $("save-status").textContent = text; $("save-status").className = kind; }
function draftKey() { return `etr-draft:${pack}:${team ? `${signedReviewer}:` : ""}${current}`; }
function buildFields() {
  for (const [key,title,hint,choices] of specs) {
    const field = document.createElement("section"); field.className = "field"; field.id = `field-${key}`;
    const heading = document.createElement("div"); heading.className = "field-title";
    const name = document.createElement("span"); name.textContent = title;
    const small = document.createElement("small"); small.textContent = hint; heading.append(name,small);
    const group = document.createElement("div"); group.className = "choices"; group.setAttribute("role","group"); group.setAttribute("aria-label",title);
    for (const [value,label] of choices) {
      const button = document.createElement("button"); button.type="button"; button.textContent=label;
      button.dataset.field=key; button.dataset.value=value;
      button.addEventListener("click", () => { values[key]=value; paintChoices(); changed(); }); group.append(button);
    }
    field.append(heading,group); $("fields").append(field);
  }
}
function paintChoices() {
  const showNotes=values.annotation_verdict==="problem" || Boolean((values.notes||"").trim());
  $("notes").hidden=!showNotes;document.querySelector(".notes-label").hidden=!showNotes;
  document.querySelectorAll(".choices button").forEach(button => {
    const selected = button.dataset.field==="domain" && ["useful_real","closeup_product","kitchen","web_misc"].includes(values.domain) ? "non_target" : values[button.dataset.field];
    const active = selected===button.dataset.value;
    button.classList.toggle("active",active); button.setAttribute("aria-pressed",String(active));
  });
}
function visibleItems() {
  const filter = $("filter").value;
  return items.filter(item => filter==="all" || (filter==="pending" && !item.version) ||
    (filter==="uncertain" && item.version && verdictOf(item,item.review)!=="ok") || (filter==="negative" && !item.knife_count));
}
function verdictOf(item, review) {
  if(review.annotation_verdict) return review.annotation_verdict;
  if(review.label_quality==="good" && review.bbox_completeness==="yes" && review.exclude==="no" && (item.knife_count || review.negative_knife_absence==="yes")) return "ok";
  if(["bad","minor_issue"].includes(review.label_quality) || review.bbox_completeness==="no" || review.negative_knife_absence==="no" || review.exclude==="yes") return "problem";
  return "unclear";
}
function refreshProgress() {
  const reviewed = items.filter(item=>item.version).length;
  const held = items.filter(item=>item.version && verdictOf(item,item.review)!=="ok").length;
  $("progress-text").textContent=`${reviewed} / ${items.length}장 검수 기록`;
  $("progress").max=items.length; $("progress").value=reviewed;
  $("counts").textContent=`미검수 ${items.length-reviewed} · 재확인 ${held}`;
  $("jump").replaceChildren();
  for (const item of visibleItems()) {
    const option = document.createElement("option"); option.value=item.id;
    option.textContent=`${item.version ? "✓" : "·"} ${String(item.id+1).padStart(3,"0")} ${item.name}`;
    $("jump").append(option);
  }
  $("jump").value=current;
}
function show(index) {
  current=index; const item=items[current];
  values={...item.review}; delete values.reviewed_at;
  const draft=localStorage.getItem(draftKey()); let restoredDraft=false;
  if (draft) { try { const saved=JSON.parse(draft); if(saved.version===item.version) {values={...saved.fields}; restoredDraft=true;} } catch {} }
  if (!values.annotation_verdict && item.version && !restoredDraft) {
    values.annotation_verdict=verdictOf(item,values);
  }
  values.review_schema="simple-v2";
  values.reviewer=values.reviewer || rememberReviewer;
  if(team) values.reviewer=signedReviewer;
  $("reviewer").value=values.reviewer || ""; $("notes").value=values.notes || "";
  $("sample-number").textContent=`${String(current+1).padStart(2,"0")} / ${items.length}`;
  $("filename").textContent=item.name;
  $("kind").textContent=item.knife_count ? `칼 라벨 ${item.knife_count}개` : "칼 라벨 0개 · 실제 부재 확인";
  $("kind").classList.toggle("negative",!item.knife_count);
  $("dimensions").textContent=`${item.width} × ${item.height}`;
  $("original").href=item.image_url;
  $("verdict-guide").textContent=item.knife_count ? "정상 = 보이는 칼이 모두 정확한 박스 안에 있음. 틀린 박스·칼 누락은 ‘문제 있음’." : "정상 = 실제 칼이 없음. 칼이 하나라도 보이면 ‘문제 있음’.";
  $("saved-badge").textContent=item.version ? "검수 기록 있음" : "미검수";
  $("image-svg").setAttribute("viewBox",`0 0 ${item.width} ${item.height}`);
  $("image-svg").replaceChildren();
  const ns="http://www.w3.org/2000/svg";
  const image=document.createElementNS(ns,"image");
  image.setAttribute("href",item.image_url); image.setAttribute("width",item.width); image.setAttribute("height",item.height);
  $("image-svg").append(image);
  for (const [left,top,right,bottom] of item.boxes) {
    const rect=document.createElementNS(ns,"rect"); rect.classList.add("bbox");
    for (const [key,value] of Object.entries({x:left,y:top,width:right-left,height:bottom-top,fill:"none",stroke:"#00ff7f","stroke-width":2,"vector-effect":"non-scaling-stroke"})) rect.setAttribute(key,value);
    $("image-svg").append(rect);
  }
  $("image-view").classList.remove("zoom2","zoom3"); $("image-view").scrollTop=0; $("image-view").scrollLeft=0; $("zoom").textContent="확대 1×";
  dirty=restoredDraft; paintChoices(); refreshProgress();
  if(team){document.querySelectorAll(".choices button").forEach(button=>button.disabled=!item.editable);$("notes").readOnly=!item.editable;$("save-next").disabled=!item.editable;$("saved-badge").textContent=item.editable?"내 담당":"읽기 전용 · 다음 미검수 받기";}
  $("previous").disabled=current===0; $("next").disabled=current===items.length-1;
  status(item.version ? `자동 저장됨 · 수정 ${item.version}회` : "선택하면 자동 저장됩니다.",item.version?"saved":"");
  if(window.matchMedia("(max-width: 750px)").matches)window.scrollTo(0,0);
}
function complete() {
  return ["domain","annotation_verdict","reviewer"].every(key=>(values[key]||"").trim()) &&
    (values.annotation_verdict!=="problem" || (values.notes||"").trim());
}
function changed() {
  dirty=true;
  localStorage.setItem(draftKey(),JSON.stringify({version:items[current].version,fields:values}));
  clearTimeout(timer);
  status(complete()?"저장 대기…":"임시 입력 보관 중 · 필수 항목을 선택해주세요.");
  if(complete()) timer=setTimeout(()=>save(),500);
}
async function save(force=false) {
  clearTimeout(timer);
  if (!dirty) return true;
  if (!complete()) { if(force) status("이름과 두 질문을 확인해주세요. 문제 있음은 한 줄 메모가 필요합니다.","error"); return false; }
  if(saving) return false;
  saving=true; const id=current; const captured=JSON.stringify(values); let succeeded=false;
  $("save-next").disabled=true; status("저장 중…");
  try {
    const response=await fetch(apiUrl("/api/review"),{method:"POST",headers:{"Content-Type":"application/json","X-Review-Token":csrf},body:JSON.stringify({id,version:items[id].version,fields:values})});
    const result=await response.json(); if(!response.ok) throw new Error(result.error || "저장 실패");
    items[id].version=result.version; items[id].review=result.review;
    succeeded=true;
    if(id===current && captured===JSON.stringify(values)) {dirty=false; localStorage.removeItem(draftKey());}
    else if(id===current) {localStorage.setItem(draftKey(),JSON.stringify({version:result.version,fields:values}));}
    $("saved-badge").textContent="검수 기록 있음"; refreshProgress(); status(team?"자동 저장됨 · PC13에 기록했습니다.":"자동 저장됨 · 이 PC에 안전하게 기록했습니다.","saved");
    return !dirty;
  } catch(error) {status(error.message,"error"); return false;}
  finally {saving=false; $("save-next").disabled=false; if(succeeded && dirty && complete()) timer=setTimeout(()=>save(),500);}
}
async function move(delta) {
  if(saving) return;
  if(dirty && complete() && !await save()) return;
  if(team&&delta>0){await claimNext();return;}
  const visible=visibleItems(); const next=delta>0 ? visible.find(item=>item.id>current) : [...visible].reverse().find(item=>item.id<current);
  if(next) show(next.id); else status("이 필터의 마지막 이미지입니다.");
}
async function claimNext(){if(teamAdmin){status("관리자 계정은 현황 확인용입니다. 개인 검수 계정으로 로그인해주세요.");return;}const response=await fetch(apiUrl("/api/claim"),{method:"POST",headers:{"Content-Type":"application/json","X-Review-Token":csrf},body:"{}"});if(!response.ok){status("담당 배정 실패 · 새로고침 후 다시 시도해주세요.","error");return;}const result=await response.json();if(result.id===null){status("배정 가능한 미검수가 없습니다. 후보 목록에서 다른 데이터셋을 선택하세요.","saved");return;}items[result.id].editable=true;show(result.id);}
async function jump(index) {if(saving)return; if(dirty && complete() && !await save())return; show(index);}
function quick(kind) {
  values.annotation_verdict={keep:"ok",reject:"problem",hold:"unclear"}[kind];
  paintChoices(); changed();
}
async function init() {
  buildFields();
  const response=await fetch(apiUrl("/api/items")); if(!response.ok){if(teamDataset&&response.status===401)location.href="/login";throw new Error("검수 자료를 읽지 못했습니다.");}
  const data=await response.json();
  if(data.review_schema!=="simple-v2") throw new Error("이 서버는 이전 버전입니다. 간단 검수 주소 http://127.0.0.1:8768 을 열어주세요. 기존 저장 기록은 그대로 유지됩니다.");
  items=data.items; csrf=data.csrf; pack=data.pack_hash;
  team=Boolean(data.team);signedReviewer=data.reviewer||"";teamAdmin=Boolean(data.admin);
  if(team){
    document.body.classList.add("team-review");
    if(!teamAdmin && data.reviewer_id)localStorage.setItem(`etr-last-pack:${data.reviewer_id}`,teamDataset);
    document.title=`${teamDataset} · 팀 이미지 검수`;$("reviewer").readOnly=true;document.querySelector(".reviewer-label").textContent="검수자 · 선택한 이름";document.querySelector(".brand strong").textContent=`${signedReviewer} · 검수`;document.querySelector(".local-badge").textContent="PC13 중앙 저장";const back=document.querySelector(".top-actions a");back.href="/";back.textContent="후보 목록 ↗";document.querySelector(".brand div span").textContent=`EDGE THREAT RESPONSE / ${teamDataset}`;document.querySelector("footer").textContent="원본은 수정하지 않습니다. 판정·수정 이력은 PC13에 저장됩니다. 학습·권리 승인은 별도입니다.";document.querySelector(".image-note").textContent="초록 박스 = 원본의 칼 라벨 · 위치와 누락을 확인해주세요";$("next").textContent="다음 미검수 받기 →";
  }
  $("reviewer").addEventListener("input",()=>{values.reviewer=$("reviewer").value;rememberReviewer=values.reviewer;localStorage.setItem("etr-reviewer",rememberReviewer);changed();});
  $("notes").addEventListener("input",()=>{values.notes=$("notes").value;changed();});
  $("previous").addEventListener("click",()=>move(-1));$("next").addEventListener("click",()=>move(1));
  $("save-next").addEventListener("click",async()=>{if(await save(true))await move(1);});
  $("jump").addEventListener("change",()=>jump(Number($("jump").value)));
  $("filter").addEventListener("change",async()=>{if(dirty&&complete())await save();refreshProgress();const visible=visibleItems();if(visible.length)await jump(visible[0].id);else status("이 조건에 해당하는 이미지가 없습니다.");});
  $("show-boxes").addEventListener("change",()=>$("image-view").classList.toggle("hide-boxes",!$("show-boxes").checked));
  $("zoom").addEventListener("click",()=>{const view=$("image-view");const zoom=view.classList.contains("zoom2")?3:view.classList.contains("zoom3")?1:2;view.classList.remove("zoom2","zoom3");if(zoom>1)view.classList.add(`zoom${zoom}`);$("zoom").textContent=`확대 ${zoom}×`;});
  document.querySelectorAll("[data-quick]").forEach(button=>button.addEventListener("click",()=>quick(button.dataset.quick)));
  document.addEventListener("keydown",event=>{if(["INPUT","TEXTAREA","SELECT"].includes(event.target.tagName)||event.ctrlKey||event.metaKey||event.altKey)return;if(event.key==="ArrowRight"){event.preventDefault();move(1);}if(event.key==="ArrowLeft"){event.preventDefault();move(-1);}if(["1","2","3"].includes(event.key)){event.preventDefault();quick({"1":"keep","2":"reject","3":"hold"}[event.key]);}});
  const first=items.find(item=>!item.version); show(first?first.id:0);
  if(team&&!teamAdmin)await claimNext();
}
init().catch(error=>status(error.message,"error"));
