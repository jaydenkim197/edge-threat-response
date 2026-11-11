"use strict";
const $ = id => document.getElementById(id);
const simpleSpecs = [
  ["domain", "① CCTV형 장면인가요?", "위에서 비스듬히 · 넓은 시야", [["target_cctv","CCTV형"],["non_target","그 외"],["unclear","모르겠음"]]],
  ["annotation_verdict", "② 칼 라벨은 정상인가요?", "박스 위치 + 칼 누락을 한 번에 확인", [["ok","정상"],["problem","문제 있음"],["unclear","모르겠음"]]],
];
const videoPresenceSpec = ["knife_presence", "② 칼이 보이나요?", "보이는 칼마다 박스를 확인하거나 추가하세요.", [["yes","칼 있음"],["no","칼 없음"],["unclear","모르겠음"]]];
let items = [], current = 0, csrf = "", pack = "", values = {}, dirty = false, saving = false, timer;
let reviewSchema = "simple-v2";
const teamDataset=location.pathname.startsWith("/review/")?location.pathname.split("/")[2]:"";
const apiUrl=path=>path+(teamDataset?`?dataset=${encodeURIComponent(teamDataset)}`:"");
let team=false, signedReviewer="", teamAdmin=false;
let leaseEnabled=false, leaseActivity=false, heartbeatBusy=false;
const svgNS = "http://www.w3.org/2000/svg";
let boxMode = "browse", selectedBox = -1, boxDrag = null;

function videoReview() { return reviewSchema === "video-box-v1"; }
function canEditBoxes() { return videoReview() && (!team || Boolean(items[current]?.editable)); }

function paintBoxControls() {
  const editable = canEditBoxes();
  $("box-add").disabled = $("box-edit").disabled = !editable;
  $("box-remove").disabled = !editable || selectedBox < 0;
  $("box-add").setAttribute("aria-pressed", String(boxMode === "draw"));
  $("box-edit").setAttribute("aria-pressed", String(boxMode === "edit"));
  $("image-svg").classList.toggle("box-drag-mode", editable && boxMode !== "browse");
  const count = values.reviewed_boxes.length;
  $("box-count").textContent = selectedBox < 0 ? count + "개" : (selectedBox + 1) + " / " + count + " 선택";
}

function svgRect(group, bounds, classes, attributes = {}) {
  const [left, top, right, bottom] = bounds;
  const rect = document.createElementNS(svgNS, "rect");
  rect.setAttribute("class", classes);
  for (const [key, value] of Object.entries({
    x: left, y: top, width: right - left, height: bottom - top, ...attributes
  })) rect.setAttribute(key, value);
  group.append(rect);
  return rect;
}

function paintVideoBoxes() {
  const group = $("box-layer");
  if (!group) return;
  group.replaceChildren();
  values.reviewed_boxes.forEach((box, index) => {
    const active = index === selectedBox;
    const bounds = boxDrag?.index === index ? boxDrag.preview : box;
    svgRect(group, bounds, "bbox video-bbox" + (active ? " selected" : ""), {"data-box-index": index});
    if (!active || boxMode !== "edit" || !canEditBoxes()) return;
    const matrix = $("image-svg").getScreenCTM();
    if (!matrix) return;
    const [left, top, right, bottom] = bounds;
    const radius = Math.min(9 / Math.hypot(matrix.a, matrix.b), (right - left) / 3, (bottom - top) / 3);
    [[left, top], [right, top], [left, bottom], [right, bottom]].forEach(([x, y], corner) => {
      svgRect(group, [x - radius, y - radius, x + radius, y + radius], "bbox box-handle", {
        "data-box-index": index, "data-box-corner": corner
      });
    });
  });
  if (boxDrag?.index === -1) svgRect(group, boxDrag.preview, "bbox video-bbox selected box-preview");
  paintBoxControls();
}

function setBoxMode(mode) {
  boxMode = mode;
  if (mode !== "browse") {
    $("show-boxes").checked = true;
    $("image-view").classList.remove("hide-boxes");
  }
  paintVideoBoxes();
}

function imagePoint(event, inside = false) {
  const matrix = $("image-svg").getScreenCTM();
  if (!matrix) return null;
  const {x, y} = new DOMPoint(event.clientX, event.clientY).matrixTransform(matrix.inverse());
  const {width, height} = items[current];
  if (inside && (x < 0 || y < 0 || x > width || y > height)) return null;
  return [Math.min(Math.max(x, 0), width), Math.min(Math.max(y, 0), height)];
}

function beginBoxDrag(event) {
  if (!canEditBoxes() || !event.isPrimary || event.button !== 0 || boxDrag) return;
  const index = Number(event.target.dataset.boxIndex ?? -1);
  if (boxMode !== "draw") {
    selectedBox = index;
    if (boxMode !== "edit" || index < 0) { paintVideoBoxes(); return; }
  }
  const point = imagePoint(event, boxMode === "draw");
  if (!point) return;
  const box = boxMode === "draw" ? [...point, ...point] : values.reviewed_boxes[index];
  boxDrag = {
    id: event.pointerId, point, original: box, preview: box, index: boxMode === "draw" ? -1 : index,
    corner: event.target.dataset.boxCorner, moved: false,
  };
  $("image-svg").setPointerCapture(event.pointerId);
  if (event.pointerType === "mouse") event.preventDefault();
  paintVideoBoxes();
}

function updateBoxDrag(event) {
  if (!boxDrag || boxDrag.id !== event.pointerId) return;
  const point = imagePoint(event);
  if (!point) return;
  const {index, original, corner, point: [startX, startY]} = boxDrag;
  const [x, y] = point;
  if (x !== startX || y !== startY) boxDrag.moved = true;
  const [left, top, right, bottom] = original;
  if (index < 0) {
    boxDrag.preview = [Math.min(startX, x), Math.min(startY, y), Math.max(startX, x), Math.max(startY, y)];
  } else if (corner !== undefined) {
    const rightEdge = Number(corner) % 2;
    const bottomEdge = Number(corner) >= 2;
    boxDrag.preview = [
      rightEdge ? left : Math.min(x, right - 1),
      bottomEdge ? top : Math.min(y, bottom - 1),
      rightEdge ? Math.max(x, left + 1) : right,
      bottomEdge ? Math.max(y, top + 1) : bottom,
    ];
  } else {
    const {width, height} = items[current];
    const dx = Math.min(Math.max(x - startX, -left), width - right);
    const dy = Math.min(Math.max(y - startY, -top), height - bottom);
    boxDrag.preview = [left + dx, top + dy, right + dx, bottom + dy];
  }
  paintVideoBoxes();
}

function finishBoxDrag(event) {
  if (!boxDrag || boxDrag.id !== event.pointerId) return;
  if (event.type === "pointerup") updateBoxDrag(event);
  const {index, preview, moved} = boxDrag;
  boxDrag = null;
  const [left, top, right, bottom] = preview.map(coordinate => Math.round(coordinate * 100) / 100);
  if (event.type === "pointerup" && canEditBoxes() && moved && right > left && bottom > top) {
    const bounds = [left, top, right, bottom];
    if (index < 0) {
      values.reviewed_boxes.push(bounds);
      selectedBox = values.reviewed_boxes.length - 1;
    } else {
      values.reviewed_boxes[index] = bounds;
    }
    values.knife_presence = "yes";
    paintChoices();
    changed();
  }
  paintVideoBoxes();
}

function setupBoxEditor() {
  $("box-toolbar").hidden = false;
  $("box-add").addEventListener("click", () => setBoxMode(boxMode === "draw" ? "browse" : "draw"));
  $("box-edit").addEventListener("click", () => setBoxMode(boxMode === "edit" ? "browse" : "edit"));
  $("box-remove").addEventListener("click", () => {
    if (!canEditBoxes() || selectedBox < 0) return;
    values.reviewed_boxes.splice(selectedBox, 1);
    selectedBox = -1;
    paintVideoBoxes();
    changed();
  });
  const svg = $("image-svg");
  svg.addEventListener("pointerdown", beginBoxDrag);
  svg.addEventListener("pointermove", updateBoxDrag);
  for (const type of ["pointerup", "pointercancel", "lostpointercapture"]) svg.addEventListener(type, finishBoxDrag);
}

function assignmentLost(id) {
  items[id].editable=false;
  if(id!==current)return;
  clearTimeout(timer);
  document.querySelectorAll(".choices button").forEach(button=>button.disabled=true);
  $("notes").readOnly=true;$("save-next").disabled=false;$("save-next").textContent="다음 미검수 받기 →";$("next").disabled=false;
  if(videoReview()) {boxDrag=null; setBoxMode("browse");}
  $("saved-badge").textContent="배정 만료 · 입력은 임시 보관";
  status("배정이 만료됐습니다. 작성 중인 내용은 임시 보관됩니다. ‘다음 미검수 받기’를 눌러주세요.","error");
}
async function heartbeat() {
  if(!leaseEnabled || !team || teamAdmin || !leaseActivity || heartbeatBusy || document.visibilityState!=="visible")return;
  const id=current;if(!items[id]?.editable || items[id].version)return;
  leaseActivity=false;heartbeatBusy=true;
  try {
    const response=await fetch(apiUrl("/api/heartbeat"),{method:"POST",headers:{"Content-Type":"application/json","X-Review-Token":csrf},body:JSON.stringify({id})});
    if(response.status===409)assignmentLost(id);
    else if(!response.ok)leaseActivity=true;
  } catch {leaseActivity=true;}
  finally {heartbeatBusy=false;}
}
let rememberReviewer = localStorage.getItem("etr-reviewer") || "";
function status(text, kind="") { $("save-status").textContent = text; $("save-status").className = kind; }
function draftKey() { return `etr-draft:${pack}:${team ? `${signedReviewer}:` : ""}${current}`; }
function buildFields() {
  const specs = videoReview() ? [simpleSpecs[0], videoPresenceSpec] : simpleSpecs;
  for (const [key,title,hint,choices] of specs) {
    const field = document.createElement("section"); field.className = "field"; field.id = `field-${key}`;
    const heading = document.createElement("div"); heading.className = "field-title";
    const name = document.createElement("span"); name.textContent = title;
    const small = document.createElement("small"); small.textContent = hint; heading.append(name,small);
    const group = document.createElement("div"); group.className = "choices"; group.setAttribute("role","group"); group.setAttribute("aria-label",title);
    for (const [value,label] of choices) {
      const button = document.createElement("button"); button.type="button"; button.textContent=label;
      button.dataset.field=key; button.dataset.value=value;
      button.addEventListener("click", () => {
        values[key]=value;
        if(videoReview() && key==="knife_presence" && value!=="yes") {
          values.reviewed_boxes=[]; selectedBox=-1; setBoxMode("browse");
        }
        paintChoices(); changed();
      }); group.append(button);
    }
    field.append(heading,group); $("fields").append(field);
  }
}
function paintChoices() {
  const showNotes=videoReview() || values.annotation_verdict==="problem" || Boolean((values.notes||"").trim());
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
  if(videoReview()) {
    values.reviewed_boxes=(values.reviewed_boxes || item.boxes).map(box=>[...box]);
    delete values.annotation_verdict;
    selectedBox=-1; boxDrag=null; boxMode="browse";
  }
  if (!videoReview() && !values.annotation_verdict && item.version && !restoredDraft) {
    values.annotation_verdict=verdictOf(item,values);
  }
  values.review_schema=reviewSchema;
  values.reviewer=values.reviewer || rememberReviewer;
  if(team) values.reviewer=signedReviewer;
  $("reviewer").value=values.reviewer || ""; $("notes").value=values.notes || "";
  $("sample-number").textContent=`${String(current+1).padStart(2,"0")} / ${items.length}`;
  $("filename").textContent=item.name;
  $("kind").textContent=videoReview() ? (item.knife_count ? `모델 제안 ${item.knife_count}개` : "미검출 후보") :
    (item.knife_count ? `칼 라벨 ${item.knife_count}개` : "칼 라벨 0개 · 실제 부재 확인");
  $("kind").classList.toggle("negative",!item.knife_count);
  $("dimensions").textContent=`${item.width} × ${item.height}${item.batch_id ? ` · ${item.batch_id}` : ""}`;
  $("original").href=item.image_url;
  $("verdict-guide").textContent=videoReview() ?
    "칼이 보이면 모든 칼에 박스를 표시하세요. 애매한 장면은 모르겠음을 선택하세요." : item.knife_count ? "정상 = 보이는 칼이 모두 정확한 박스 안에 있음. 틀린 박스·칼 누락은 ‘문제 있음’." : "정상 = 실제 칼이 없음. 칼이 하나라도 보이면 ‘문제 있음’.";
  $("saved-badge").textContent=item.version ? "검수 기록 있음" : "미검수";
  $("image-svg").setAttribute("viewBox",`0 0 ${item.width} ${item.height}`);
  $("image-svg").replaceChildren();
  const ns="http://www.w3.org/2000/svg";
  const image=document.createElementNS(ns,"image");
  image.setAttribute("href",item.image_url); image.setAttribute("width",item.width); image.setAttribute("height",item.height);
  $("image-svg").append(image);
  if(videoReview()) {
    const layer = document.createElementNS(svgNS, "g");
    layer.id = "box-layer";
    $("image-svg").append(layer);
  }
  for (const [left,top,right,bottom] of (videoReview() ? [] : item.boxes)) {
    const rect=document.createElementNS(ns,"rect"); rect.classList.add("bbox");
    for (const [key,value] of Object.entries({x:left,y:top,width:right-left,height:bottom-top,fill:"none",stroke:"#00ff7f","stroke-width":2,"vector-effect":"non-scaling-stroke"})) rect.setAttribute(key,value);
    $("image-svg").append(rect);
  }
  $("image-view").classList.remove("zoom2","zoom3"); $("image-view").scrollTop=0; $("image-view").scrollLeft=0; $("zoom").textContent="확대 1×";
  dirty=restoredDraft; paintChoices(); refreshProgress();
  if(videoReview()) paintVideoBoxes();
  if(team){document.querySelectorAll(".choices button").forEach(button=>button.disabled=!item.editable);$("notes").readOnly=!item.editable;$("save-next").disabled=teamAdmin;$("save-next").textContent=item.editable?"저장하고 다음 →":"다음 미검수 받기 →";$("saved-badge").textContent=item.editable?"내 담당":"읽기 전용 · 다음 미검수 받기";}
  $("previous").disabled=current===0; $("next").disabled=!team&&current===items.length-1;
  if(videoReview()) {
    status(restoredDraft ? "임시 입력을 불러왔습니다." : item.version ? `저장됨 · 수정 ${item.version}회` : "판정 후 저장하고 다음을 누르세요.", item.version && !restoredDraft ? "saved" : "");
  } else {
    status(item.version ? `자동 저장됨 · 수정 ${item.version}회` : "선택하면 자동 저장됩니다.",item.version?"saved":"");
  }
  if(window.matchMedia("(max-width: 750px)").matches)window.scrollTo(0,0);
}
function complete() {
  if(videoReview()) return Boolean(values.domain && (values.reviewer||"").trim()) &&
    (values.knife_presence==="yes" ? values.reviewed_boxes.length > 0 : ["no","unclear"].includes(values.knife_presence));
  return ["domain","annotation_verdict","reviewer"].every(key=>(values[key]||"").trim()) &&
    (values.annotation_verdict!=="problem" || (values.notes||"").trim());
}
function changed() {
  dirty=true;
  localStorage.setItem(draftKey(),JSON.stringify({version:items[current].version,fields:values}));
  clearTimeout(timer);
  status(complete() ? (videoReview() ? "임시 저장됨 · 저장하고 다음을 누르세요." : "저장 대기…") : "임시 입력 보관 중 · 필수 항목을 선택해주세요.");
  if(!videoReview() && complete()) timer=setTimeout(()=>save(),500);
}
async function save(force=false) {
  clearTimeout(timer);
  if(videoReview() && force && !complete()) {
    status("장면 유형과 칼 유무를 선택하세요. 칼이 있으면 박스를 한 개 이상 표시해야 합니다.", "error");
    return false;
  }
  if (!dirty) return true;
  if(team&&!items[current].editable)return false;
  if (!complete()) { if(force) status("이름과 두 질문을 확인해주세요. 문제 있음은 한 줄 메모가 필요합니다.","error"); return false; }
  if(saving) return false;
  saving=true; const id=current; const captured=JSON.stringify(values); let succeeded=false;
  $("save-next").disabled=true; status("저장 중…");
  try {
    const response=await fetch(apiUrl("/api/review"),{method:"POST",headers:{"Content-Type":"application/json","X-Review-Token":csrf},body:JSON.stringify({id,version:items[id].version,fields:values})});
    const result=await response.json(); if(result.assignment_lost){assignmentLost(id);return false;} if(!response.ok) throw new Error(result.error || "저장 실패");
    items[id].version=result.version; items[id].review=result.review;
    succeeded=true;
    if(id===current && captured===JSON.stringify(values)) {dirty=false; localStorage.removeItem(draftKey());}
    else if(id===current) {localStorage.setItem(draftKey(),JSON.stringify({version:result.version,fields:values}));}
    $("saved-badge").textContent="검수 기록 있음"; refreshProgress(); status(videoReview() ? "박스와 판정을 저장했습니다." : team?"자동 저장됨 · PC13에 기록했습니다.":"자동 저장됨 · 이 PC에 안전하게 기록했습니다.","saved");
    return !dirty;
  } catch(error) {status(error.message,"error"); return false;}
  finally {saving=false; $("save-next").disabled=team&&teamAdmin; if(!videoReview() && succeeded && dirty && complete()) timer=setTimeout(()=>save(),500);}
}
async function move(delta) {
  if(saving) return;
  if(!videoReview() && dirty && complete() && (!team||items[current].editable) && !await save()) return;
  if(team&&delta>0){await claimNext();return;}
  const visible=visibleItems(); const next=delta>0 ? visible.find(item=>item.id>current) : [...visible].reverse().find(item=>item.id<current);
  if(next) show(next.id); else status("이 필터의 마지막 이미지입니다.");
}
async function claimNext(){
  if(teamAdmin){status("관리자 계정은 현황 확인용입니다. 개인 검수 계정으로 로그인해주세요.");return;}
  const response=await fetch(apiUrl("/api/claim"),{method:"POST",headers:{"Content-Type":"application/json","X-Review-Token":csrf},body:JSON.stringify({known_total:items.length})});
  if(!response.ok){status("담당 배정 실패 · 새로고침 후 다시 시도해주세요.","error");return;}
  const result=await response.json();
  if(result.refresh_required){
    const refreshed=await fetch(apiUrl("/api/items"));
    if(!refreshed.ok){status("새 표본을 불러오지 못했습니다. 새로고침해주세요.","error");return;}
    const data=await refreshed.json();
    if(data.items.length<=items.length){status("새 표본 준비 중입니다. 잠시 후 새로고침해주세요.");return;}
    items=data.items;csrf=data.csrf;await claimNext();return;
  }
  if(result.id===null){status(result.pending_assigned?"남은 사진은 다른 검수자에게 배정돼 있습니다. 15분간 활동이 없으면 자동 회수됩니다.":"이 데이터셋의 검수가 완료됐습니다. 다른 데이터셋을 선택하세요.","saved");return;}
  items[result.id].editable=true;show(result.id);
}
async function jump(index) {if(saving)return; if(!videoReview() && dirty && complete() && (!team||items[current].editable) && !await save())return; show(index);}
function quick(kind) {
  if(videoReview() || (team&&!items[current].editable))return;
  values.annotation_verdict={keep:"ok",reject:"problem",hold:"unclear"}[kind];
  paintChoices(); changed();
}
async function init() {
  const response=await fetch(apiUrl("/api/items")); if(!response.ok){if(teamDataset&&response.status===401)location.href="/login";throw new Error("검수 자료를 읽지 못했습니다.");}
  const data=await response.json();
  if(!["simple-v2","video-box-v1"].includes(data.review_schema)) throw new Error("이 서버는 이전 버전입니다. 간단 검수 주소 http://127.0.0.1:8768 을 열어주세요. 기존 저장 기록은 그대로 유지됩니다.");
  reviewSchema=data.review_schema;
  buildFields();
  items=data.items; csrf=data.csrf; pack=data.pack_hash;
  team=Boolean(data.team);signedReviewer=data.reviewer||"";teamAdmin=Boolean(data.admin);
  leaseEnabled=Boolean(data.assignment_timeout_seconds);
  if(leaseEnabled){
    for(const event of ["pointerdown","keydown","input","scroll"])document.addEventListener(event,()=>{leaseActivity=true;},{passive:true,capture:true});
    document.addEventListener("visibilitychange",()=>{if(document.visibilityState==="visible"){leaseActivity=true;heartbeat();}});
    setInterval(heartbeat,30000);
  }
  if(team){
    document.body.classList.add("team-review");
    if(!teamAdmin && data.reviewer_id)localStorage.setItem(`etr-last-pack:${data.reviewer_id}`,teamDataset);
    document.title=`${teamDataset} · 팀 이미지 검수`;$("reviewer").readOnly=true;document.querySelector(".reviewer-label").textContent="검수자 · 선택한 이름";document.querySelector(".brand strong").textContent=`${signedReviewer} · 검수`;document.querySelector(".local-badge").textContent="PC13 중앙 저장";const back=document.querySelector(".top-actions a");back.href="/";back.textContent="후보 목록 ↗";document.querySelector(".brand div span").textContent=`EDGE THREAT RESPONSE / ${teamDataset}`;document.querySelector("footer").textContent="원본은 수정하지 않습니다. 판정·수정 이력은 PC13에 저장됩니다. 학습·권리 승인은 별도입니다.";document.querySelector(".image-note").textContent="초록 박스 = 원본의 칼 라벨 · 위치와 누락을 확인해주세요";$("next").textContent="다음 미검수 받기 →";
  }
  if(videoReview()) {
    setupBoxEditor();
    document.body.classList.add("video-box-review");
    document.querySelector(".image-note").textContent="초록 박스는 편집할 칼 후보입니다. 박스를 눌러 선택하세요.";
    document.querySelector(".notes-label").textContent="메모 · 선택";
    $("notes").placeholder="확인이 필요한 내용";
    document.querySelector(".review-panel details p").textContent="칼이 보이면 박스 추가를 누른 뒤 이미지 위를 드래그하세요. 박스 조절을 켜면 박스 안을 드래그해 옮기거나 모서리를 드래그해 크기를 바꿀 수 있습니다.";
    for (const tip of document.querySelectorAll(".review-panel details p:not(:first-of-type)")) tip.hidden=true;
  }
  $("reviewer").addEventListener("input",()=>{values.reviewer=$("reviewer").value;rememberReviewer=values.reviewer;localStorage.setItem("etr-reviewer",rememberReviewer);changed();});
  $("notes").addEventListener("input",()=>{values.notes=$("notes").value;changed();});
  $("previous").addEventListener("click",()=>move(-1));$("next").addEventListener("click",()=>move(1));
  $("save-next").addEventListener("click",async()=>{if(team&&!items[current].editable){await claimNext();return;}if(await save(true))await move(1);});
  $("jump").addEventListener("change",()=>jump(Number($("jump").value)));
  $("filter").addEventListener("change",async()=>{if(!videoReview()&&dirty&&complete())await save();refreshProgress();const visible=visibleItems();if(visible.length)await jump(visible[0].id);else status("이 조건에 해당하는 이미지가 없습니다.");});
  $("show-boxes").addEventListener("change",()=>$("image-view").classList.toggle("hide-boxes",!$("show-boxes").checked));
  $("zoom").addEventListener("click",()=>{const view=$("image-view");const zoom=view.classList.contains("zoom2")?3:view.classList.contains("zoom3")?1:2;view.classList.remove("zoom2","zoom3");if(zoom>1)view.classList.add(`zoom${zoom}`);$("zoom").textContent=`확대 ${zoom}×`;if(videoReview())paintVideoBoxes();});
  document.querySelectorAll("[data-quick]").forEach(button=>button.addEventListener("click",()=>quick(button.dataset.quick)));
  document.addEventListener("keydown",event=>{if(["INPUT","TEXTAREA","SELECT"].includes(event.target.tagName)||event.ctrlKey||event.metaKey||event.altKey)return;if(event.key==="ArrowRight"){event.preventDefault();move(1);}if(event.key==="ArrowLeft"){event.preventDefault();move(-1);}if(!videoReview() && ["1","2","3"].includes(event.key)){event.preventDefault();quick({"1":"keep","2":"reject","3":"hold"}[event.key]);}});
  const first=items.find(item=>!item.version); show(first?first.id:0);
  if(team&&!teamAdmin)await claimNext();
}
init().catch(error=>status(error.message,"error"));
