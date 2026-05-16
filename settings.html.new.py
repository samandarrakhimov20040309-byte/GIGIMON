import re

with open("/Applications/gigimon/app/static/settings.html", "r") as f:
    content = f.read()

old_section = """<!-- AI Integration Section -->
<section class="col-span-12 lg:col-span-6 rounded-2xl p-8" style="background-color: #0f1930; border: 1px solid rgba(59, 191, 250, 0.15);">
<h2 class="text-xl font-bold font-headline mb-6 flex items-center gap-2" style="color: white;">
<span class="material-symbols-outlined" style="color: var(--accent-color, #3bbffa);">smart_toy</span>
AI Integration
</h2>
<p class="text-sm mb-6" style="color: #a3aac4;">AI tahlil uchun OpenAI API kalitingizni kiriting. Kalit <a href="https://platform.openai.com/api-keys" target="_blank" style="color: var(--accent-color, #3bbffa);" class="underline">platform.openai.com</a> dan olinadi.</p>
<div class="space-y-4">
<div>
<label class="text-xs font-bold uppercase tracking-widest mb-2 block" style="color: #a3aac4;">OpenAI API Key</label>
<input id="ai-api-key" class="w-full rounded-xl px-4 py-3 border-none focus:ring-2 font-mono text-sm" style="background-color: #192540; color: #dee5ff;" type="password" placeholder="sk-..."/>
</div>
<div class="flex items-center gap-3">
<button onclick="saveAiApiKey()" class="px-6 py-3 rounded-xl font-bold text-sm transition-all" style="background-color: var(--accent-color, #3bbffa); color: #00374d;">
Saqlash
</button>
<span id="ai-key-status" class="text-xs" style="color: #a3aac4;"></span>
</div>
</div>
</section>"""

new_section = """<!-- AI Integration Section -->
<section class="col-span-12 lg:col-span-6 rounded-2xl p-8" style="background-color: #0f1930; border: 1px solid rgba(59, 191, 250, 0.15);">
<h2 class="text-xl font-bold font-headline mb-6 flex items-center gap-2" style="color: white;">
<span class="material-symbols-outlined" style="color: var(--accent-color, #3bbffa);">smart_toy</span>
AI Integration
</h2>
<p class="text-sm mb-6" style="color: #a3aac4;">AI tahlil uchun OpenAI yoki Gemini API kalitingizni kiriting.</p>
<div class="space-y-4">
<div>
<label class="text-xs font-bold uppercase tracking-widest mb-2 block" style="color: #a3aac4;">AI Provayder</label>
<select id="ai-provider" class="w-full rounded-xl px-4 py-3 border-none focus:ring-2 text-sm" style="background-color: #192540; color: #dee5ff;">
<option value="openai">OpenAI</option>
<option value="gemini">Gemini (bepul)</option>
</select>
</div>
<div>
<label class="text-xs font-bold uppercase tracking-widest mb-2 block" style="color: #a3aac4;">API Key</label>
<input id="ai-api-key" class="w-full rounded-xl px-4 py-3 border-none focus:ring-2 font-mono text-sm" style="background-color: #192540; color: #dee5ff;" type="password" placeholder="API kalitingiz..."/>
</div>
<div>
<p class="text-xs" style="color: #a3aac4;">
OpenAI kaliti: <a href="https://platform.openai.com/api-keys" target="_blank" style="color: var(--accent-color, #3bbffa);" class="underline">platform.openai.com</a>
&middot;
Gemini kaliti: <a href="https://aistudio.google.com/apikey" target="_blank" style="color: var(--accent-color, #3bbffa);" class="underline">aistudio.google.com</a>
</p>
</div>
<div class="flex items-center gap-3">
<button onclick="saveAiApiKey()" class="px-6 py-3 rounded-xl font-bold text-sm transition-all" style="background-color: var(--accent-color, #3bbffa); color: #00374d;">
Saqlash
</button>
<span id="ai-key-status" class="text-xs" style="color: #a3aac4;"></span>
</div>
</div>
</section>"""

content = content.replace(old_section, new_section)

# Update loadAiApiKey to also load provider
old_load = """            if (settings['ai_api_key']) {
                document.getElementById('ai-api-key').value = settings['ai_api_key'];
                document.getElementById('ai-key-status').textContent = "Kalit o'rnatilgan";
                document.getElementById('ai-key-status').style.color = '#6bff8f';
            }"""

new_load = """            if (settings['ai_api_key']) {
                document.getElementById('ai-api-key').value = settings['ai_api_key'];
                document.getElementById('ai-key-status').textContent = "Kalit o'rnatilgan";
                document.getElementById('ai-key-status').style.color = '#6bff8f';
            }
            if (settings['ai_provider']) {
                document.getElementById('ai-provider').value = settings['ai_provider'];
            }"""

content = content.replace(old_load, new_load)

# Update saveAiApiKey to include provider
old_save = """        const res = await fetch(`${API_BASE}/settings/batch`, {
            method: 'PUT',
            headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
            body: JSON.stringify({ ai_api_key: key })
        });"""

new_save = """        const provider = document.getElementById('ai-provider').value;
        const res = await fetch(`${API_BASE}/settings/batch`, {
            method: 'PUT',
            headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
            body: JSON.stringify({ ai_api_key: key, ai_provider: provider })
        });"""

content = content.replace(old_save, new_save)

with open("/Applications/gigimon/app/static/settings.html", "w") as f:
    f.write(content)

print("OK")
