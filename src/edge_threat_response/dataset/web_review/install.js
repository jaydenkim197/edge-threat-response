"use strict";
const installHelp=document.getElementById("install-help");
const installButton=document.getElementById("install-button");
const standalone=window.matchMedia("(display-mode: standalone)").matches || navigator.standalone===true;
if(installHelp){
  installHelp.hidden=standalone;
  const ios=/iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.platform==="MacIntel" && navigator.maxTouchPoints>1);
  document.getElementById("install-instructions").textContent=ios
    ? "Safari에서 열고 공유 → 홈 화면에 추가 → 추가를 누르세요. ‘웹 앱으로 열기’가 보이면 켜주세요. 홈 화면 아이콘으로 최근 검수를 이어갈 수 있습니다."
    : "Chrome의 ⋮ 메뉴에서 ‘홈 화면에 추가’ 또는 ‘설치 및 바로가기 만들기 → 설치’를 선택하세요. 홈 화면 아이콘으로 최근 검수를 이어갈 수 있습니다.";
}
let installPrompt=null;
window.addEventListener("beforeinstallprompt",event=>{
  if(!installHelp || standalone)return;
  event.preventDefault();installPrompt=event;installButton.hidden=false;
});
if(installButton)installButton.addEventListener("click",async()=>{
  if(!installPrompt)return;
  installButton.disabled=true;
  try{await installPrompt.prompt();await installPrompt.userChoice;}
  finally{installPrompt=null;installButton.hidden=true;installButton.disabled=false;}
});
window.addEventListener("appinstalled",()=>{if(installHelp)installHelp.hidden=true;});
