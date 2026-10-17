const basePrefix = typeof window.BASE_PREFIX === "string" ? window.BASE_PREFIX : "/shorturl";

const form = document.getElementById("shorten-form");
const originalUrlInput = document.getElementById("original-url");
const customDescriptionInput = document.getElementById("custom-description");
const customAliasInput = document.getElementById("custom-alias");
const expiresAtInput = document.getElementById("expires-at");
const submitBtn = document.getElementById("submit-btn");
const submitBtnText = document.getElementById("submit-btn-text");
const formError = document.getElementById("form-error");

const resultCard = document.getElementById("result-card");
const resultShortUrl = document.getElementById("result-short-url");
const resultMetaTitle = document.getElementById("result-meta-title");
const resultMetaDesc = document.getElementById("result-meta-desc");
const resultOriginalUrl = document.getElementById("result-original-url");
const resultCopyBtn = document.getElementById("result-copy-btn");
const resultQrBtn = document.getElementById("result-qr-btn");

const statTotalLinks = document.getElementById("stat-total-links");
const statTotalClicks = document.getElementById("stat-total-clicks");
const statActiveLinks = document.getElementById("stat-active-links");

const urlTableBody = document.getElementById("url-table-body");
const searchInput = document.getElementById("search-input");
const refreshBtn = document.getElementById("refresh-btn");
const purgeExpiredBtn = document.getElementById("purge-expired-btn");

const qrModal = document.getElementById("qr-modal");
const qrContainer = document.getElementById("qr-container");
const qrUrlLabel = document.getElementById("qr-url-label");
const closeQrModal = document.getElementById("close-qr-modal");
const closeQrBtn = document.getElementById("close-qr-btn");

const toastEl = document.getElementById("toast");
const domainPreview = document.getElementById("domain-preview");
const hostPrefix = document.getElementById("host-prefix");

let allUrls = [];
let toastTimer = null;

// Set current host + subpath preview
const origin = window.location.origin;
if (domainPreview) {
    domainPreview.textContent = `${origin}${basePrefix}/{code}`;
}
if (hostPrefix) {
    hostPrefix.textContent = `${origin}${basePrefix}/`;
}

function showToast(message) {
    toastEl.textContent = message;
    toastEl.classList.remove("hidden");
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
        toastEl.classList.add("hidden");
    }, 2800);
}

function formatDateTime(isoStr) {
    if (!isoStr) return "-";
    const d = new Date(isoStr);
    if (isNaN(d.getTime())) return "-";
    return d.toLocaleString("ko-KR", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
    });
}

async function copyToClipboard(text) {
    try {
        await navigator.clipboard.writeText(text);
        showToast("단축 링크가 클립보드에 복사되었습니다!");
    } catch {
        const textarea = document.createElement("textarea");
        textarea.value = text;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand("copy");
        document.body.removeChild(textarea);
        showToast("단축 링크가 복사되었습니다!");
    }
}

function openQrModal(shortUrl) {
    qrContainer.innerHTML = "";
    qrUrlLabel.textContent = shortUrl;
    if (typeof QRCode !== "undefined") {
        new QRCode(qrContainer, {
            text: shortUrl,
            width: 180,
            height: 180,
            colorDark: "#0f172a",
            colorLight: "#ffffff",
            correctLevel: QRCode.CorrectLevel.M,
        });
    } else {
        qrContainer.textContent = "QR 라이브러리를 불러올 수 없습니다.";
    }
    qrModal.classList.remove("hidden");
    qrModal.classList.add("flex");
}

function closeQr() {
    qrModal.classList.add("hidden");
    qrModal.classList.remove("flex");
}

closeQrModal.addEventListener("click", closeQr);
closeQrBtn.addEventListener("click", closeQr);
qrModal.addEventListener("click", (e) => {
    if (e.target === qrModal) closeQr();
});

function updateStats(items) {
    const totalLinks = items.length;
    const totalClicks = items.reduce((acc, cur) => acc + (cur.clicks || 0), 0);
    const activeLinks = items.filter((item) => !item.is_expired).length;

    statTotalLinks.textContent = totalLinks.toLocaleString();
    statTotalClicks.textContent = totalClicks.toLocaleString();
    statActiveLinks.textContent = activeLinks.toLocaleString();
}

function escapeHtml(str) {
    return String(str || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function renderTable() {
    const query = (searchInput.value || "").trim().toLowerCase();
    const filtered = allUrls.filter((item) => {
        if (!query) return true;
        return (
            (item.short_code || "").toLowerCase().includes(query) ||
            (item.original_url || "").toLowerCase().includes(query) ||
            (item.short_url || "").toLowerCase().includes(query) ||
            (item.custom_description || "").toLowerCase().includes(query) ||
            (item.meta_title || "").toLowerCase().includes(query) ||
            (item.meta_description || "").toLowerCase().includes(query)
        );
    });

    if (filtered.length === 0) {
        urlTableBody.innerHTML = `
            <tr>
                <td colspan="5" class="py-12 text-center text-slate-500">
                    ${query ? "검색 조건과 일치하는 단축 링크가 없습니다." : "아직 생성된 단축 URL이 없습니다. 위 입력창에서 첫 단축 링크를 만들어 보세요!"}
                </td>
            </tr>
        `;
        return;
    }

    urlTableBody.innerHTML = filtered
        .map((item) => {
            const statusBadge = item.is_expired
                ? `<span class="inline-block px-2 py-0.5 text-[11px] font-medium rounded-full bg-rose-500/15 text-rose-300 border border-rose-500/30">만료(소멸대상)</span>`
                : `<span class="inline-block px-2 py-0.5 text-[11px] font-medium rounded-full bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">활성</span>`;

            const expiryText = item.expires_at
                ? `<div class="text-xs text-slate-400 mt-0.5">만료: ${formatDateTime(item.expires_at)}</div>`
                : `<div class="text-xs text-slate-500 mt-0.5">만료: 생성 후 1년</div>`;

            const metaUpdatedText = item.meta_updated_at
                ? `<div class="text-[11px] text-slate-500 mt-1">메타 수집: ${formatDateTime(item.meta_updated_at)}</div>`
                : "";

            const thumbHtml = item.meta_image
                ? `<img src="${escapeHtml(item.meta_image)}" alt="" class="w-16 h-12 rounded-lg object-cover border border-slate-700 shrink-0 bg-slate-950" onerror="this.style.display='none'" />`
                : `<div class="w-16 h-12 rounded-lg border border-slate-800 bg-slate-950/80 flex items-center justify-center text-[10px] text-slate-500 shrink-0">No Image</div>`;

            const titleText = item.meta_title || item.original_url;
            const descText = item.meta_description || "수집된 요약 설명이 없습니다.";
            const customDescBadge = item.custom_description
                ? `<span class="inline-block px-1.5 py-0.5 text-[10px] font-medium rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 mr-1">사용자 설명</span>`
                : `<span class="inline-block px-1.5 py-0.5 text-[10px] font-medium rounded bg-slate-800 text-slate-400 border border-slate-700 mr-1">타겟 메타</span>`;

            const shortHref = `${basePrefix}/${encodeURIComponent(item.short_code)}`;

            return `
                <tr class="hover:bg-slate-800/40 transition">
                    <td class="py-4 px-4 sm:px-6 align-top">
                        <div class="flex flex-col gap-1.5">
                            <div class="flex items-center flex-wrap gap-1.5">
                                <a href="${shortHref}" target="_blank" class="font-bold text-indigo-400 hover:text-indigo-300 underline decoration-indigo-500/40 break-all">
                                    ${escapeHtml(item.short_url)}
                                </a>
                                ${statusBadge}
                            </div>
                            <span class="text-[11px] text-slate-500">클릭 시 대기 없이 즉시 타겟 이동</span>
                        </div>
                    </td>
                    <td class="py-4 px-4 align-top max-w-xs sm:max-w-md">
                        <div class="flex items-start gap-3">
                            ${thumbHtml}
                            <div class="min-w-0 flex-1 space-y-1">
                                <div class="flex items-center gap-1.5">
                                    ${item.favicon_url ? `<img src="${escapeHtml(item.favicon_url)}" alt="" class="w-3.5 h-3.5 rounded-sm shrink-0" onerror="this.style.display='none'" />` : ""}
                                    <p class="font-semibold text-slate-100 text-xs sm:text-sm truncate" title="${escapeHtml(titleText)}">
                                        ${escapeHtml(titleText)}
                                    </p>
                                </div>
                                <p class="text-xs text-slate-300 line-clamp-2 break-words" title="${escapeHtml(descText)}">
                                    ${customDescBadge}${escapeHtml(descText)}
                                </p>
                                <a href="${escapeHtml(item.original_url)}" target="_blank" rel="noopener noreferrer" class="block text-[11px] font-mono text-indigo-300/80 hover:text-indigo-300 truncate" title="${escapeHtml(item.original_url)}">
                                    ${escapeHtml(item.original_url)}
                                </a>
                            </div>
                        </div>
                    </td>
                    <td class="py-4 px-4 align-top text-center">
                        <span class="inline-flex items-center justify-center px-2.5 py-1 rounded-lg bg-slate-800 text-indigo-300 font-semibold text-xs">
                            ${item.clicks.toLocaleString()}회
                        </span>
                    </td>
                    <td class="py-4 px-4 align-top whitespace-nowrap text-xs text-slate-300">
                        <div>생성: ${formatDateTime(item.created_at)}</div>
                        ${expiryText}
                        ${metaUpdatedText}
                    </td>
                    <td class="py-4 px-4 sm:px-6 align-top text-right whitespace-nowrap">
                        <div class="inline-flex items-center gap-1.5 flex-wrap justify-end">
                            <button
                                type="button"
                                data-edit-desc="${escapeHtml(item.short_code)}"
                                data-current-desc="${escapeHtml(item.custom_description || "")}"
                                title="프리뷰 메타정보에 노출되는 사용자 링크 설명을 수정합니다"
                                class="px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium border border-slate-700 transition cursor-pointer"
                            >
                                설명수정
                            </button>
                            <button
                                type="button"
                                data-refresh-meta="${escapeHtml(item.short_code)}"
                                title="타겟 사이트의 메타정보(제목, 설명, 이미지)를 강제로 다시 수집합니다"
                                class="px-2.5 py-1.5 rounded-lg bg-indigo-500/20 hover:bg-indigo-500/30 text-indigo-300 text-xs font-medium border border-indigo-500/30 transition cursor-pointer flex items-center gap-1"
                            >
                                <span>↻ 메타갱신</span>
                            </button>
                            <button
                                type="button"
                                data-copy="${escapeHtml(item.short_url)}"
                                class="px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium border border-slate-700 transition cursor-pointer"
                            >
                                복사
                            </button>
                            <button
                                type="button"
                                data-qr="${escapeHtml(item.short_url)}"
                                class="px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium border border-slate-700 transition cursor-pointer"
                            >
                                QR
                            </button>
                            <button
                                type="button"
                                data-delete="${escapeHtml(item.short_code)}"
                                class="px-2.5 py-1.5 rounded-lg bg-rose-500/15 hover:bg-rose-500/25 text-rose-300 text-xs font-medium border border-rose-500/30 transition cursor-pointer"
                            >
                                삭제
                            </button>
                        </div>
                    </td>
                </tr>
            `;
        })
        .join("");
}

async function fetchUrls() {
    try {
        const res = await fetch(`${basePrefix}/api/urls`);
        if (!res.ok) throw new Error("목록을 불러오지 못했습니다.");
        allUrls = await res.json();
        updateStats(allUrls);
        renderTable();
    } catch (err) {
        showToast(err.message || "오류가 발생했습니다.");
    }
}

form.addEventListener("submit", async (e) => {
    e.preventDefault();
    formError.classList.add("hidden");

    const original_url = originalUrlInput.value.trim();
    const custom_description = customDescriptionInput ? (customDescriptionInput.value.trim() || null) : null;
    const custom_alias = customAliasInput.value.trim() || null;
    const expiresRaw = expiresAtInput.value;
    let expires_at = null;

    if (expiresRaw) {
        const parsed = new Date(expiresRaw);
        if (!isNaN(parsed.getTime())) {
            expires_at = parsed.toISOString();
        }
    }

    submitBtn.disabled = true;
    if (submitBtnText) submitBtnText.textContent = "메타 수집 및 생성 중...";

    try {
        const res = await fetch(`${basePrefix}/api/urls`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ original_url, custom_description, custom_alias, expires_at }),
        });

        if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            let detailMsg = "단축 URL 생성에 실패했습니다.";
            if (typeof errData.detail === "string") {
                detailMsg = errData.detail;
            } else if (Array.isArray(errData.detail) && errData.detail.length > 0) {
                detailMsg = errData.detail[0].msg || detailMsg;
            }
            throw new Error(detailMsg);
        }

        const created = await res.json();
        resultShortUrl.textContent = created.short_url;
        resultShortUrl.href = `${basePrefix}/${encodeURIComponent(created.short_code)}`;
        resultMetaTitle.textContent = `프리뷰 제목: ${created.meta_title || "-"}`;
        if (resultMetaDesc) {
            resultMetaDesc.textContent = `프리뷰 설명: ${created.meta_description || "-"}`;
        }
        resultOriginalUrl.textContent = `원본: ${created.original_url}`;
        resultCopyBtn.onclick = () => copyToClipboard(created.short_url);
        resultQrBtn.onclick = () => openQrModal(created.short_url);
        resultCard.classList.remove("hidden");

        originalUrlInput.value = "";
        if (customDescriptionInput) customDescriptionInput.value = "";
        customAliasInput.value = "";
        expiresAtInput.value = "";

        showToast("단축 링크 및 프리뷰 메타정보가 생성되었습니다!");
        await fetchUrls();
    } catch (err) {
        formError.textContent = err.message;
        formError.classList.remove("hidden");
    } finally {
        submitBtn.disabled = false;
        if (submitBtnText) submitBtnText.textContent = "단축 URL 생성";
    }
});

urlTableBody.addEventListener("click", async (e) => {
    const editDescBtn = e.target.closest("[data-edit-desc]");
    if (editDescBtn) {
        const code = editDescBtn.getAttribute("data-edit-desc");
        const currentDesc = editDescBtn.getAttribute("data-current-desc") || "";
        const nextDesc = prompt(
            `'${basePrefix}/${code}' 링크의 사용자 설명 텍스트를 입력하세요.\n(비워두면 타겟 사이트 기본 메타 설명을 사용합니다)`,
            currentDesc
        );
        if (nextDesc === null) return;
        try {
            const res = await fetch(`${basePrefix}/api/urls/${encodeURIComponent(code)}/description`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ custom_description: nextDesc.trim() || null }),
            });
            if (!res.ok) throw new Error("링크 설명 수정에 실패했습니다.");
            showToast(`'${basePrefix}/${code}' 링크 설명이 메타정보에 반영되었습니다.`);
            await fetchUrls();
        } catch (err) {
            showToast(err.message);
        }
        return;
    }

    const refreshMetaBtn = e.target.closest("[data-refresh-meta]");
    if (refreshMetaBtn) {
        const code = refreshMetaBtn.getAttribute("data-refresh-meta");
        const originalLabel = refreshMetaBtn.innerHTML;
        refreshMetaBtn.disabled = true;
        refreshMetaBtn.innerHTML = `<span>갱신 중...</span>`;
        try {
            const res = await fetch(`${basePrefix}/api/urls/${encodeURIComponent(code)}/refresh-meta`, {
                method: "POST",
            });
            if (!res.ok) throw new Error("메타정보 갱신에 실패했습니다.");
            showToast(`'${basePrefix}/${code}' 링크의 타겟 메타정보가 최신 상태로 갱신되었습니다!`);
            await fetchUrls();
        } catch (err) {
            showToast(err.message);
            refreshMetaBtn.disabled = false;
            refreshMetaBtn.innerHTML = originalLabel;
        }
        return;
    }

    const copyBtn = e.target.closest("[data-copy]");
    if (copyBtn) {
        const url = copyBtn.getAttribute("data-copy");
        copyToClipboard(url);
        return;
    }

    const qrBtn = e.target.closest("[data-qr]");
    if (qrBtn) {
        const url = qrBtn.getAttribute("data-qr");
        openQrModal(url);
        return;
    }

    const deleteBtn = e.target.closest("[data-delete]");
    if (deleteBtn) {
        const code = deleteBtn.getAttribute("data-delete");
        if (!confirm(`'${basePrefix}/${code}' 단축 링크를 삭제하시겠습니까?`)) return;
        try {
            const res = await fetch(`${basePrefix}/api/urls/${encodeURIComponent(code)}`, {
                method: "DELETE",
            });
            if (!res.ok) throw new Error("삭제에 실패했습니다.");
            showToast(`'${basePrefix}/${code}' 링크가 삭제되었습니다.`);
            await fetchUrls();
        } catch (err) {
            showToast(err.message);
        }
    }
});

if (purgeExpiredBtn) {
    purgeExpiredBtn.addEventListener("click", async () => {
        try {
            const res = await fetch(`${basePrefix}/api/urls/expired/purge`, { method: "DELETE" });
            if (!res.ok) throw new Error("만료 링크 정리에 실패했습니다.");
            const data = await res.json();
            showToast(data.message || "만료된 링크가 정리되었습니다.");
            await fetchUrls();
        } catch (err) {
            showToast(err.message);
        }
    });
}

searchInput.addEventListener("input", renderTable);
refreshBtn.addEventListener("click", fetchUrls);

// Initial load
fetchUrls();
