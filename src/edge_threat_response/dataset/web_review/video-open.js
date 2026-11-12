"use strict";

async function openVideoReview() {
  const status = document.getElementById("video-open-status");
  const publicAccess = status.dataset.public === "1";
  const token = publicAccess ? "" : location.hash.slice(1);
  try {
    if (status.dataset.resume !== "1") {
      if (!publicAccess && !token) throw new Error("팀에서 받은 영상 검수 공유 링크를 열어주세요.");
      const response = await fetch("/api/video/open", {
        method: "POST",
        headers: {"Content-Type": "application/json", "X-Review-Token": status.dataset.csrf},
        body: JSON.stringify({token})
      });
      if (!response.ok) {
        const result = await response.json();
        throw new Error(result.error);
      }
    }
    location.replace("/?resume=1&video=1");
  } catch (error) {
    status.textContent = error.message || "검수 화면을 열 수 없습니다. 페이지를 다시 열어주세요.";
  }
}

openVideoReview();
