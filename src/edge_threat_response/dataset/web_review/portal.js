"use strict";
let portalCsrf="";
const el=id=>document.getElementById(id);
function node(tag,text){const element=document.createElement(tag);element.textContent=text;return element;}
async function api(path,body){const response=await fetch(path,body===undefined?{}:{method:"POST",headers:{"Content-Type":"application/json","X-Review-Token":portalCsrf},body:JSON.stringify(body)});if(response.status===401){location.href="/login";throw new Error("로그인이 필요합니다.");}const result=await response.json();if(!response.ok)throw new Error(result.error||"요청 실패");return result;}
async function refreshUsers(){const data=await api("/api/users");el("users").replaceChildren();for(const user of data.users){const row=node("p",`${user.name} · ${user.active?"활성":"비활성"}`);if(!user.admin&&user.active){const button=node("button","접속 해제");button.className="small-button";button.onclick=async()=>{await api(`/api/users/${user.id}/disable`,{});await refreshUsers();};row.append(" ",button);}el("users").append(row);}}
async function initPortal(){
  const data=await api("/api/catalog");portalCsrf=data.csrf;el("identity").textContent=data.user.name;
  el("datasets").replaceChildren();el("resume-review").hidden=true;
  if(data.video_login_required){
    const link=node("a","영상 검수 열기 →");link.className="button dark";link.href="/video/login";
    el("datasets").append(link);
  }
  const last=localStorage.getItem(`etr-last-pack:${data.user.id}`);
  const resume=data.datasets.find(item=>item.id===last && item.available && item.remaining);
  if(resume && !data.user.admin){
    el("resume-review").hidden=false;el("resume-review").href=`/review/${resume.id}`;
    el("resume-review").textContent=`${resume.name} 이어하기 →`;
    if(new URLSearchParams(location.search).get("resume")==="1"){location.replace(el("resume-review").href);return;}
  }
  if(!data.user.admin && new URLSearchParams(location.search).get("video")==="1"){
    const first=data.datasets.find(item=>item.available && item.remaining && item.review_schema?.startsWith("video-"));
    if(first){location.replace(`/review/${first.id}`);return;}
  }
  for(const item of data.datasets){
    const card=document.createElement("article");card.className="progress-card dataset-card";
    card.append(node("h2",item.name),node("p",item.available?`미검수 ${item.remaining}장 · ${item.reviewed} / ${item.total}장 완료 · 내 검수 ${item.mine}장`:`준비 중: ${item.reason||"확인 필요"}`));
    if(item.available){const link=node("a",data.user.admin?"검수 현황 보기 →":item.reviewed===item.total?"검수 완료 · 기록 보기 →":"검수 시작 →");link.className="button dark";link.href=`/review/${item.id}`;card.append(link);}
    const info=node("details","");info.append(node("summary","데이터셋 정보"),node("p",item.role),node("p",item.note||""));
    if(item.batch_count>1)info.append(node("p",`${item.batch_count}개 표본 묶음 · 기존 기록을 유지하며 이어서 검수합니다.`));
    if(item.source_url){const provenance=node("a","출처·이용 조건 ↗");provenance.href=item.source_url;provenance.target="_blank";provenance.rel="noopener";info.append(provenance);}card.append(info);
    el("datasets").append(card);
  }
  el("logout").textContent=data.name_login && !data.user.admin?"이름 바꾸기":"로그아웃";
  el("logout").onclick=async()=>{try{await api("/api/logout",{});location.href="/login";}catch(error){el("portal-status").textContent=error.message;}};
  if(data.user.admin){
    el("admin-panel").hidden=false;await refreshUsers();
    if(data.video_link_login){
      el("invite-help").textContent="공유 링크를 열면 브라우저별 검수 세션이 생성됩니다.";
      el("invite-form").hidden=true;
      return;
    }
    el("invite-help").textContent=data.name_login?"이름을 등록하면 팀원의 이름 선택 목록에 표시됩니다.":"이름을 등록하면 개인 코드를 발급합니다.";
    el("invite-form").onsubmit=async event=>{event.preventDefault();try{
      const result=await api("/api/users",{name:el("invite-name").value});
      el("invite-result").replaceChildren(node("strong",data.name_login?`${result.name} 등록 완료`:`${result.name}의 접속 코드: `));
      if(!data.name_login || data.video_review_enabled)el("invite-result").append(node("code",result.code),node("p","개인 코드는 지금만 표시합니다. 본인에게 전달하세요."));
      el("invite-name").value="";await refreshUsers();
    }catch(error){el("portal-status").textContent=error.message;}};
  }
}
initPortal().catch(error=>el("portal-status").textContent=error.message);
window.addEventListener("pageshow",event=>{if(event.persisted)initPortal().catch(error=>el("portal-status").textContent=error.message);});
