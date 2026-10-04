"use strict";
let portalCsrf="";
const el=id=>document.getElementById(id);
function node(tag,text){const element=document.createElement(tag);element.textContent=text;return element;}
async function api(path,body){const response=await fetch(path,body===undefined?{}:{method:"POST",headers:{"Content-Type":"application/json","X-Review-Token":portalCsrf},body:JSON.stringify(body)});if(response.status===401){location.href="/login";throw new Error("로그인이 필요합니다.");}const result=await response.json();if(!response.ok)throw new Error(result.error||"요청 실패");return result;}
async function refreshUsers(){const data=await api("/api/users");el("users").replaceChildren();for(const user of data.users){const row=node("p",`${user.name} · ${user.active?"활성":"비활성"}`);if(!user.admin&&user.active){const button=node("button","접속 해제");button.className="small-button";button.onclick=async()=>{await api(`/api/users/${user.id}/disable`,{});await refreshUsers();};row.append(" ",button);}el("users").append(row);}}
async function initPortal(){
  const data=await api("/api/catalog");portalCsrf=data.csrf;el("identity").textContent=data.user.name;
  const last=localStorage.getItem(`etr-last-pack:${data.user.id}`);
  const resume=data.datasets.find(item=>item.id===last && item.available && item.reviewed<item.total);
  if(resume && !data.user.admin){
    el("resume-review").hidden=false;el("resume-review").href=`/review/${resume.id}`;
    el("resume-review").textContent=`${resume.name} 이어하기 →`;
    if(new URLSearchParams(location.search).get("resume")==="1"){location.replace(el("resume-review").href);return;}
  }
  for(const item of data.datasets){
    const card=document.createElement("article");card.className="progress-card dataset-card";
    card.append(node("h2",item.name),node("p",item.available?`${item.reviewed} / ${item.total}장 완료 · 내 검수 ${item.mine}장`:`준비 중: ${item.reason||"확인 필요"}`));
    if(item.available){const link=node("a",data.user.admin?"검수 현황 보기 →":item.reviewed===item.total?"검수 완료 · 기록 보기 →":"검수 시작 →");link.className="button dark";link.href=`/review/${item.id}`;card.append(link);}
    const info=node("details","");info.append(node("summary","데이터셋 정보"),node("p",item.role),node("p",item.note||""));
    if(item.batch_count>1)info.append(node("p",`${item.batch_count}개 표본 묶음 · 기존 기록을 유지하며 이어서 검수합니다.`));
    const provenance=node("a","출처·이용 조건 ↗");provenance.href=item.source_url;provenance.target="_blank";provenance.rel="noopener";info.append(provenance);card.append(info);
    el("datasets").append(card);
  }
  el("logout").textContent=data.user.admin?"로그아웃":"이름 바꾸기";
  el("logout").onclick=async()=>{try{await api("/api/logout",{});location.href="/login";}catch(error){el("portal-status").textContent=error.message;}};
  if(data.user.admin){
    el("admin-panel").hidden=false;await refreshUsers();
    el("invite-help").textContent=data.name_login?"이름을 등록하면 팀원의 이름 선택 목록에 표시됩니다.":"이름을 등록하면 개인 코드를 발급합니다.";
    el("invite-form").onsubmit=async event=>{event.preventDefault();try{
      const result=await api("/api/users",{name:el("invite-name").value});
      el("invite-result").replaceChildren(node("strong",data.name_login?`${result.name} 등록 완료`:`${result.name}의 접속 코드: `));
      if(!data.name_login)el("invite-result").append(node("code",result.code),node("p","이 코드는 지금만 표시합니다. 본인에게 전달하세요."));
      el("invite-name").value="";await refreshUsers();
    }catch(error){el("portal-status").textContent=error.message;}};
  }
}
initPortal().catch(error=>el("portal-status").textContent=error.message);
