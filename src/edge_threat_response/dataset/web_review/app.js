"use strict";
const $ = id => document.getElementById(id);
const specs = [
  ["domain", "어떤 장면인가요?", "필수", [["target_cctv","CCTV 시점"],["useful_real","일반 실사"],["closeup_product","제품·근접"],["kitchen","주방"],["web_misc","기타 웹사진"],["unclear","불명확"]]],
  ["label_quality", "칼 박스가 정확한가요?", "필수", [["good","정상"],["minor_issue","작은 문제"],["bad","명백한 오류"],["ambiguous","판단 어려움"]]],
  ["bbox_completeness", "보이는 칼이 모두 표시됐나요?", "필수 · 없으면 ‘칼 없음’ 확인", [["yes","모두 표시됨"],["no","누락 있음"],["unclear","불명확"]]],
  ["negative_knife_absence", "실제로 칼이 없는 이미지인가요?", "음성 후보 필수", [["yes","칼 없음"],["no","칼이 있음!"],["unclear","불명확"]]],
  ["exclude", "이 표본은 어떻게 처리할까요?", "필수 · 채택/학습 승인 아님", [["no","유지 후보"],["yes","제외 후보"],["uncertain","보류"]]],
  ["person_cooccurrence", "사람 동반", "선택", [["yes","있음"],["no","없음"],["unclear","불명확"]]],
  ["small_or_distant_knife", "작거나 먼 칼", "선택", [["yes","그렇다"],["no","아니다"],["unclear","불명확"]]],
  ["occlusion", "칼 가림", "선택", [["none","없음"],["partial","일부"],["severe","심함"],["unclear","불명확"]]],
];
let items = [], current = 0, csrf = "", pack = "", values = {}, dirty = false, saving = false, timer;
let rememberReviewer = localStorage.getItem("etr-reviewer") || "";
function status(text, kind="") { $("save-status").textContent = text; $("save-status").className = kind; }
function draftKey() { return `etr-draft:${pack}:${current}`; }
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
  document.querySelectorAll(".choices button").forEach(button => {
    const active = values[button.dataset.field]===button.dataset.value;
    button.classList.toggle("active",active); button.setAttribute("aria-pressed",String(active));
  });
}
function visibleItems() {
  const filter = $("filter").value;
  return items.filter(item => filter==="all" || (filter==="pending" && !item.version) ||
    (filter==="uncertain" && item.review.exclude==="uncertain") || (filter==="negative" && !item.knife_count));
}
function refreshProgress() {
  const reviewed = items.filter(item=>item.version).length;
  const excluded = items.filter(item=>item.review.exclude==="yes").length;
  const held = items.filter(item=>item.review.exclude==="uncertain").length;
  $("progress-text").textContent=`${reviewed} / ${items.length}장 검수 기록`;
  $("progress").max=items.length; $("progress").value=reviewed;
  $("counts").textContent=`미검수 ${items.length-reviewed} · 제외 후보 ${excluded} · 보류 ${held}`;
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
  values.reviewer=values.reviewer || rememberReviewer;
  $("reviewer").value=values.reviewer || ""; $("notes").value=values.notes || "";
  $("sample-number").textContent=`${String(current+1).padStart(2,"0")} / ${items.length}`;
  $("filename").textContent=item.name;
  $("kind").textContent=item.knife_count ? `칼 라벨 ${item.knife_count}개` : "칼 없음 · 음성 후보";
  $("kind").classList.toggle("negative",!item.knife_count);
  $("dimensions").textContent=`${item.width} × ${item.height}`;
  $("original").href=item.image_url;
  $("field-negative_knife_absence").hidden=!!item.knife_count;
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
  $("previous").disabled=current===0; $("next").disabled=current===items.length-1;
  status(item.version ? `자동 저장됨 · 수정 ${item.version}회` : "선택하면 자동 저장됩니다.",item.version?"saved":"");
}
function complete() {
  return ["domain","label_quality","bbox_completeness","exclude","reviewer"].every(key=>(values[key]||"").trim()) &&
    (items[current].knife_count || values.negative_knife_absence) &&
    (values.exclude==="no" || (values.notes||"").trim());
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
  if (!complete()) { if(force) status("장면·라벨·누락 여부·판정·검수자를 확인해주세요. 제외·보류 이유도 필요합니다.","error"); return false; }
  if(saving) return false;
  saving=true; const id=current; const captured=JSON.stringify(values); let succeeded=false;
  $("save-next").disabled=true; status("저장 중…");
  try {
    const response=await fetch("/api/review",{method:"POST",headers:{"Content-Type":"application/json","X-Review-Token":csrf},body:JSON.stringify({id,version:items[id].version,fields:values})});
    const result=await response.json(); if(!response.ok) throw new Error(result.error || "저장 실패");
    items[id].version=result.version; items[id].review=result.review;
    succeeded=true;
    if(id===current && captured===JSON.stringify(values)) {dirty=false; localStorage.removeItem(draftKey());}
    else if(id===current) {localStorage.setItem(draftKey(),JSON.stringify({version:result.version,fields:values}));}
    $("saved-badge").textContent="검수 기록 있음"; refreshProgress(); status("자동 저장됨 · 이 PC에 안전하게 기록했습니다.","saved");
    return !dirty;
  } catch(error) {status(error.message,"error"); return false;}
  finally {saving=false; $("save-next").disabled=false; if(succeeded && dirty && complete()) timer=setTimeout(()=>save(),500);}
}
async function move(delta) {
  if(saving) return;
  if(dirty && complete() && !await save()) return;
  const visible=visibleItems(); const next=delta>0 ? visible.find(item=>item.id>current) : [...visible].reverse().find(item=>item.id<current);
  if(next) show(next.id); else status("이 필터의 마지막 이미지입니다.");
}
async function jump(index) {if(saving)return; if(dirty && complete() && !await save())return; show(index);}
function quick(kind) {
  if(kind==="keep") {values.label_quality="good";values.exclude="no";}
  if(kind==="reject") {values.label_quality="bad";values.exclude="yes";}
  if(kind==="hold") {values.label_quality="ambiguous";values.exclude="uncertain";}
  paintChoices(); changed();
}
async function init() {
  buildFields();
  const response=await fetch("/api/items"); if(!response.ok)throw new Error("검수 자료를 읽지 못했습니다.");
  const data=await response.json(); items=data.items; csrf=data.csrf; pack=data.pack_hash;
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
}
init().catch(error=>status(error.message,"error"));
