(function() {
    'use strict';

    const STORAGE_KEY = 'gigimon_assistant_messages';
    const API_BASE = window.location.origin;
    const MAX_MSG = 50;

    let isOpen = false;
    let messages = [];
    let isSending = false;

    function getPageName() {
        const p = window.location.pathname;
        if (p.includes('dashboard')) return 'Dashboard';
        if (p.includes('add-trade')) return 'Trade Qoshish';
        if (p.includes('history')) return 'Trade Tarixi';
        if (p.includes('analytics')) return 'Tahlil';
        if (p.includes('notifications')) return 'Bildirishnomalar';
        if (p.includes('settings')) return 'Sozlamalar';
        return p;
    }

    function loadMsgs() {
        try { const s = localStorage.getItem(STORAGE_KEY); if (s) messages = JSON.parse(s); } catch(e) {}
    }
    function saveMsgs() {
        try { if (messages.length > MAX_MSG) messages = messages.slice(-MAX_MSG); localStorage.setItem(STORAGE_KEY, JSON.stringify(messages)); } catch(e) {}
    }

    function renderMsgs() {
        const c = document.getElementById('assistant-msgs');
        if (!c) return;
        c.innerHTML = messages.map(function(m) {
            var u = m.role === 'user';
            var t = m.time ? new Date(m.time).toLocaleTimeString('uz-UZ', {hour:'2-digit',minute:'2-digit'}) : '';
            return '<div style="display:flex;flex-direction:column;align-items:' + (u ? 'flex-end' : 'flex-start') + ';">' +
                '<div style="max-width:85%;padding:10px 14px;border-radius:12px;font-size:13px;line-height:1.5;color:' + (u ? '#00374d' : '#dee5ff') + ';background:' + (u ? 'var(--accent-color,#3bbffa)' : '#192540') + ';' + (!u ? 'border:1px solid rgba(59,191,250,0.08);' : '') + '">' +
                m.text +
                '</div>' +
                (t ? '<span style="font-size:10px;color:#5a6280;margin-top:4px;' + (u ? 'margin-right:4px;' : 'margin-left:4px;') + '">' + t + '</span>' : '') +
                '</div>';
        }).join('');
        c.scrollTop = c.scrollHeight;
    }

    function addMsg(role, text) {
        messages.push({ role: role, text: text, time: Date.now() });
        saveMsgs();
        renderMsgs();
    }

    async function sendMsg() {
        if (isSending) return;
        var input = document.getElementById('asm-input');
        var btn = document.getElementById('asm-btn');
        var text = input.value.trim();
        if (!text) return;
        var token = localStorage.getItem('gigimon_token');
        if (!token) { addMsg('assistant', 'Iltimos, avval tizimga kiring.'); return; }
        addMsg('user', text);
        input.value = '';
        isSending = true;
        btn.textContent = '...';
        btn.disabled = true;
        try {
            var r = await fetch(API_BASE + '/ai/chat', {
                method: 'POST',
                headers: {'Content-Type':'application/json','Authorization':'Bearer '+token},
                body: JSON.stringify({message: text, current_page: getPageName()})
            });
            if (!r.ok) throw new Error((await r.json().catch(function(){return{}})).detail || 'Xatolik');
            var d = await r.json();
            addMsg('assistant', d.reply);
        } catch(e) {
            addMsg('assistant', 'Xatolik: AI sozlamalaringizni tekshiring.');
        }
        isSending = false;
        btn.textContent = 'Yuborish';
        btn.disabled = false;
        input.focus();
    }

    function buildUI() {
        var wrap = document.createElement('div');
        wrap.id = 'gigimon-assistant';
        wrap.style.cssText = 'position:fixed;bottom:24px;right:24px;z-index:9999;font-family:Inter,sans-serif;';

        var fab = document.createElement('button');
        fab.id = 'asm-fab';
        fab.textContent = '💬';
        fab.style.cssText = 'width:56px;height:56px;border-radius:50%;background:var(--accent-color,#3bbffa);border:none;box-shadow:0 8px 24px rgba(59,191,250,0.3);cursor:pointer;font-size:24px;color:#00374d;display:flex;align-items:center;justify-content:center;float:right;';

        var chat = document.createElement('div');
        chat.id = 'asm-chat';
        chat.style.cssText = 'display:none;width:380px;height:520px;border-radius:16px;background:#0f1930;border:1px solid rgba(59,191,250,0.15);box-shadow:0 25px 50px -12px rgba(0,0,0,0.5);overflow:hidden;flex-direction:column;margin-bottom:8px;';

        chat.innerHTML =
            '<div style="padding:16px 20px;background:#192540;border-bottom:1px solid rgba(59,191,250,0.1);display:flex;align-items:center;gap:10px;flex-shrink:0;">' +
                '<span style="width:32px;height:32px;border-radius:8px;background:rgba(59,191,250,0.15);display:flex;align-items:center;justify-content:center;font-size:16px;">☁️</span>' +
                '<div style="flex:1;"><div style="color:#dee5ff;font-weight:700;font-size:14px;">Gigimon AI</div><div style="color:#6bff8f;font-size:11px;">● Online</div></div>' +
                '<button id="asm-close" style="background:none;border:none;color:#a3aac4;cursor:pointer;font-size:20px;padding:4px;">✕</button>' +
            '</div>' +
            '<div id="assistant-msgs" style="flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:8px;"></div>' +
            '<div style="padding:12px 16px;border-top:1px solid rgba(59,191,250,0.1);display:flex;gap:8px;flex-shrink:0;background:#192540;">' +
                '<input id="asm-input" type="text" placeholder="Savolingizni yozing..." style="flex:1;background:#0f1930;border:1px solid rgba(59,191,250,0.1);border-radius:10px;padding:10px 14px;color:#dee5ff;font-size:13px;outline:none;">' +
                '<button id="asm-btn" style="background:var(--accent-color,#3bbffa);border:none;border-radius:10px;padding:10px 16px;color:#00374d;font-weight:700;font-size:13px;cursor:pointer;">Yuborish</button>' +
            '</div>';

        wrap.appendChild(chat);
        wrap.appendChild(fab);
        document.body.appendChild(wrap);
    }

    function init() {
        if (document.getElementById('gigimon-assistant')) return;
        buildUI();
        loadMsgs();
        renderMsgs();

        document.getElementById('asm-fab').onclick = function() {
            isOpen = !isOpen;
            document.getElementById('asm-chat').style.display = isOpen ? 'flex' : 'none';
            document.getElementById('asm-fab').style.display = isOpen ? 'none' : 'flex';
            if (isOpen) {
                var inp = document.getElementById('asm-input');
                if (inp) inp.focus();
                renderMsgs();
                var mc = document.getElementById('assistant-msgs');
                if (mc) mc.scrollTop = mc.scrollHeight;
            }
        };

        document.getElementById('asm-close').onclick = function() {
            isOpen = false;
            document.getElementById('asm-chat').style.display = 'none';
            document.getElementById('asm-fab').style.display = 'flex';
        };

        document.getElementById('asm-btn').onclick = sendMsg;
        document.getElementById('asm-input').onkeydown = function(e) { if (e.key === 'Enter') sendMsg(); };

        if (window.location.pathname.includes('dashboard')) {
            loadDashAdvice();
        }
    }

    async function loadDashAdvice() {
        var w = document.getElementById('ai-dashboard-widget');
        if (!w) return;
        var token = localStorage.getItem('gigimon_token');
        if (!token) return;
        try {
            var r = await fetch(API_BASE + '/ai/last-analysis', {headers:{'Authorization':'Bearer '+token}});
            if (r.ok) {
                var d = await r.json();
                if (d.has_data) {
                    var html = '<div style="padding:16px;border-radius:12px;background:rgba(59,191,250,0.08);border:1px solid rgba(59,191,250,0.12);">' +
                        '<div style="display:flex;align-items:center;gap:8px;margin-bottom:12px;"><span style="font-size:16px;">☁️</span><span style="color:#dee5ff;font-weight:700;font-size:13px;">AI Tahlil</span></div>';
                    var scores = d.scores || {};
                    var scoreLabels = {discipline:'Intizom',risk_management:'Risk Boshqaruvi',consistency:'Barqarorlik',pattern_recognition:'Pattern Aniqlash',sizing:'Pozitsiya Hajmi'};
                    var scoreKeys = Object.keys(scoreLabels);
                    var hasScores = scoreKeys.some(function(k){return scores[k] !== undefined && scores[k] !== null;});
                    if (hasScores) {
                        html += '<div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px;">';
                        scoreKeys.forEach(function(k) {
                            var v = scores[k] || 0;
                            var c = v >= 70 ? '#6bff8f' : v >= 40 ? '#ffb148' : '#ff716c';
                            html += '<span style="font-size:11px;padding:3px 10px;border-radius:20px;background:rgba(59,191,250,0.1);color:#dee5ff;border:1px solid rgba(59,191,250,0.15);">' + scoreLabels[k] + ': <span style="color:'+c+';font-weight:700;">'+v+'</span></span>';
                        });
                        html += '</div>';
                    }
                    if (d.advice_markdown) {
                        html += '<div style="color:#a3aac4;font-size:12px;line-height:1.6;margin-bottom:10px;">' + d.advice_markdown.replace(/\n/g,'<br>') + '</div>';
                    }
                    var actions = d.actions || [];
                    if (actions.length > 0) {
                        html += '<div style="font-size:11px;font-weight:700;color:#ffb148;margin-bottom:6px;">Tavsiyalar</div>';
                        actions.forEach(function(a) {
                            html += '<div style="display:flex;align-items:flex-start;gap:6px;padding:5px 0;font-size:11px;color:#a3aac4;"><span style="color:#ffb148;flex-shrink:0;">✓</span>' + a + '</div>';
                        });
                    }
                    if (d.model) {
                        html += '<div style="margin-top:8px;font-size:10px;color:#5a6280;">Model: ' + d.model + '</div>';
                    }
                    html += '</div>';
                    w.innerHTML = html;
                    return;
                }
            }
        } catch(e) {}
        try {
            var r2 = await fetch(API_BASE + '/ai/quick-analyze', {method:'POST', headers:{'Authorization':'Bearer '+token}});
            if (r2.ok) {
                var d2 = await r2.json();
                if (d2.has_trades) {
                    w.innerHTML = '<div style="padding:16px;border-radius:12px;background:rgba(59,191,250,0.08);border:1px solid rgba(59,191,250,0.12);">' +
                        '<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;"><span style="font-size:16px;">☁️</span><span style="color:#dee5ff;font-weight:700;font-size:13px;">AI Maslahat</span></div>' +
                        '<p style="color:#a3aac4;font-size:12px;line-height:1.5;margin:0;">' + d2.advice + '</p></div>';
                }
            }
        } catch(e) {}
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
