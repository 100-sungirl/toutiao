/* 今日热点 前端逻辑 (Vue 3, 无构建) */
const { createApp } = Vue;

const app = createApp({
    data() {
        return {
            route: 'home',            // home | detail | chat | mine
            user: null,               // {id,username,...}
            token: localStorage.getItem('token') || '',
            toast: '',

            // 登录弹窗
            showLogin: false,
            loginMode: 'login',
            loginForm: { username: '', password: '' },
            loginErr: '',

            // 首页
            categories: [],
            currentCat: null,         // 'recommend' 或分类id
            newsList: [], page: 1, hasMore: false, loading: false,
            hotList: [],
            searchWord: '', searchResults: null,
            recommend: [],

            // 详情
            detail: null, detailLoading: false, isFav: false,

            // AI对话
            sessions: [], currentSession: null, messages: [],
            chatInput: '', chatting: false,

            // 我的
            mineTab: 'fav',
            favList: [], historyList: [], sourceList: [],
            srcForm: { name: '', url: '', category_id: null },
        };
    },

    async mounted() {
        window.addEventListener('hashchange', () => this.onRoute());
        if (this.token) await this.fetchUser();
        this.onRoute();
    },

    methods: {
        /* ===== 基础 ===== */
        go(hash) { if (location.hash === hash) this.onRoute(); else location.hash = hash; },
        toastMsg(msg, ms = 2200) {
            this.toast = msg;
            clearTimeout(this._tt);
            this._tt = setTimeout(() => (this.toast = ''), ms);
        },
        async api(path, opts = {}) {
            const headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) };
            if (this.token) headers['Authorization'] = 'Bearer ' + this.token;
            const resp = await fetch(path, { ...opts, headers });
            if (resp.status === 401 && !path.includes('/login') && !path.includes('/register')) {
                this.logout(true); this.showLogin = true;
                throw new Error('请先登录');
            }
            if (resp.status === 429) { this.toastMsg('请求太频繁,稍后再试'); throw new Error('rate limited'); }
            const body = await resp.json().catch(() => ({}));
            if (!resp.ok) throw new Error(body.detail || body.message || ('HTTP ' + resp.status));
            return body;
        },
        fmtTime(t) {
            if (!t) return '';
            const d = new Date(t.replace ? t.replace(' ', 'T') : t);
            if (isNaN(d)) return t;
            const now = new Date();
            const diff = (now - d) / 1000;
            if (diff < 60) return '刚刚';
            if (diff < 3600) return Math.floor(diff / 60) + '分钟前';
            if (diff < 86400) return Math.floor(diff / 3600) + '小时前';
            const p = n => String(n).padStart(2, '0');
            return `${d.getMonth() + 1}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
        },

        /* ===== 路由 ===== */
        onRoute() {
            const hash = location.hash || '#/';
            const parts = hash.slice(2).split('/');
            this.route = ['home', 'chat', 'mine'].includes(parts[0]) || hash === '#/' ? (parts[0] || 'home') : parts[0];
            if (this.route === 'detail') { this.loadDetail(parts[1]); return; }
            if (this.route === 'home') this.initHome();
            if (this.route === 'chat') this.initChat();
            if (this.route === 'mine') this.initMine();
        },

        /* ===== 登录 ===== */
        async fetchUser() {
            try {
                const body = await this.api('/api/users/info');
                this.user = body.data;
            } catch (e) { /* token失效已处理 */ }
        },
        async submitLogin() {
            this.loginErr = '';
            const { username, password } = this.loginForm;
            if (!username || !password) { this.loginErr = '请输入用户名和密码'; return; }
            if (this.loginMode === 'register' && password.length < 6) { this.loginErr = '密码至少6位'; return; }
            try {
                const body = await this.api('/api/users/' + this.loginMode, {
                    method: 'POST', body: JSON.stringify({ username, password }),
                });
                this.token = body.data.token;
                this.user = body.data.user_info || body.data.userInfo;
                localStorage.setItem('token', this.token);
                this.showLogin = false;
                this.toastMsg(this.loginMode === 'login' ? '登录成功' : '注册成功');
                this.loginForm = { username: '', password: '' };
                this.onRoute(); // 重新加载当前页(推荐等需要登录的接口)
            } catch (e) { this.loginErr = e.message; }
        },
        logout(silent) {
            this.token = ''; this.user = null;
            localStorage.removeItem('token');
            if (!silent) this.toastMsg('已退出');
        },

        /* ===== 首页 ===== */
        async initHome() {
            if (!this.categories.length) {
                try {
                    const body = await this.api('/api/news/categories');
                    this.categories = (body.data || []).map(c => ({ id: c.id ?? c.category_id, name: c.name ?? c.category_name ?? c.title }));
                } catch (e) { console.warn(e); }
                if (!this.currentCat) this.selectCat(this.user ? 'recommend' : (this.categories[0] || {}).id);
            }
            if (!this.hotList.length) this.loadHot();
        },
        selectCat(id) {
            this.currentCat = id;
            this.searchResults = null;
            if (id === 'recommend') { this.loadRecommend(); return; }
            this.newsList = []; this.page = 1; this.hasMore = false;
            this.loadList(true);
        },
        async loadList(reset) {
            if (this.loading || this.currentCat === 'recommend') return;
            this.loading = true;
            try {
                const body = await this.api(`/api/news/list?categoryId=${this.currentCat}&page=${this.page}&pageSize=10`);
                const list = body.data.list || [];
                this.newsList = reset ? list : this.newsList.concat(list);
                this.hasMore = !!body.data.has_more;
            } catch (e) { console.warn(e); }
            this.loading = false;
        },
        loadMore() { this.page += 1; this.loadList(false); },
        async loadHot() {
            try {
                const body = await this.api('/api/news/hot?limit=10');
                this.hotList = body.data || [];
            } catch (e) { console.warn(e); }
        },
        async loadRecommend() {
            if (!this.user) return; // 游客显示提示
            try {
                const body = await this.api('/api/news/recommend?limit=10');
                this.recommend = body.data || [];
            } catch (e) { console.warn(e); }
        },
        async doSearch() {
            const q = this.searchWord.trim();
            if (!q) return;
            try {
                const body = await this.api('/api/news/search?q=' + encodeURIComponent(q) + '&limit=10');
                this.searchResults = body.data || [];
                this.currentCat = null;
                window.scrollTo(0, 0);
            } catch (e) { this.toastMsg('搜索失败:' + e.message); }
        },
        clearSearch() { this.searchResults = null; this.searchWord = ''; if (this.currentCat === null) this.selectCat((this.categories[0] || {}).id); },

        /* ===== 详情 ===== */
        async openDetail(id) {
            location.hash = '#/detail/' + id;
        },
        async loadDetail(id) {
            this.detail = null; this.isFav = false; this.detailLoading = true;
            window.scrollTo(0, 0);
            try {
                const body = await this.api('/api/news/detail?id=' + id);
                if (body.code !== 200) { this.detailLoading = false; return; }
                this.detail = body.data;
                if (this.user) {
                    this.api('/api/favorite/check?newsId=' + id).then(b => (this.isFav = !!(b.data && b.data.is_favorite))).catch(() => { });
                    this.api('/api/history/add', { method: 'POST', body: JSON.stringify({ newsId: +id }) }).catch(() => { });
                }
            } catch (e) { console.warn(e); }
            this.detailLoading = false;
        },
        async toggleFav() {
            if (!this.user) { this.showLogin = true; return; }
            try {
                if (this.isFav) {
                    await this.api('/api/favorite/remove?newsId=' + this.detail.id, { method: 'DELETE' });
                    this.isFav = false; this.toastMsg('已取消收藏');
                } else {
                    await this.api('/api/favorite/add', { method: 'POST', body: JSON.stringify({ newsId: this.detail.id }) });
                    this.isFav = true; this.toastMsg('收藏成功');
                }
            } catch (e) { this.toastMsg('操作失败:' + e.message); }
        },
        askAiAbout() {
            this.chatInput = '';
            location.hash = '#/chat';
            const q = '帮我介绍一下这篇新闻:《' + this.detail.title + '》讲了什么?';
            // 等聊天页初始化完成后自动发送
            setTimeout(() => this.sendMsg(q), 300);
        },

        /* ===== AI对话 ===== */
        async initChat() {
            if (!this.user) { this.showLogin = true; this.toastMsg('AI对话需要先登录'); return; }
            if (!this.sessions.length) await this.loadSessions();
        },
        async loadSessions() {
            try {
                const body = await this.api('/api/chat/sessions');
                this.sessions = (body.data && body.data.sessions) || [];
            } catch (e) { console.warn(e); }
        },
        async newSession() {
            try {
                const body = await this.api('/api/chat/sessions', { method: 'POST', body: JSON.stringify({ title: '新会话' }) });
                await this.loadSessions();
                this.openSession(body.data.session_id);
            } catch (e) { this.toastMsg('创建会话失败'); }
        },
        async openSession(sid) {
            this.currentSession = sid;
            try {
                const body = await this.api(`/api/chat/sessions/${sid}/messages`);
                this.messages = ((body.data && body.data.messages) || []).map(m => ({
                    role: m.role, content: m.content, sources: m.sources, msgId: m.id, rating: m.rating || 0,
                }));
                this.$nextTick(() => this.scrollBottom());
            } catch (e) { console.warn(e); }
        },
        async delSession(sid) {
            if (!confirm('删除该会话及全部消息?')) return;
            try {
                await this.api('/api/chat/sessions/' + sid, { method: 'DELETE' });
                if (this.currentSession === sid) { this.currentSession = null; this.messages = []; }
                this.loadSessions();
            } catch (e) { this.toastMsg('删除失败'); }
        },
        async sendMsg(text) {
            const q = (text || this.chatInput).trim();
            if (!q || this.chatting) return;
            if (!this.user) { this.showLogin = true; return; }
            this.chatInput = '';
            this.chatting = true;

            try {
                // 没有会话就自动创建(标题取问题前30字)
                if (!this.currentSession) {
                    const body = await this.api('/api/chat/sessions', { method: 'POST', body: JSON.stringify({ title: q.slice(0, 30) }) });
                    this.currentSession = body.data.session_id;
                    this.loadSessions();
                }
                this.messages.push({ role: 'user', content: q });
                const ai = { role: 'assistant', content: '', sources: null, streaming: true, msgId: null, rating: 0 };
                this.messages.push(ai);
                this.scrollBottom();

                const resp = await fetch('/api/chat/stream', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + this.token },
                    body: JSON.stringify({ message: q, session_id: this.currentSession }),
                });
                if (!resp.ok || !resp.body) throw new Error('HTTP ' + resp.status);

                const reader = resp.body.getReader();
                const decoder = new TextDecoder();
                let buf = '';
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    buf += decoder.decode(value, { stream: true });
                    const frames = buf.split('\n\n');
                    buf = frames.pop();
                    for (const f of frames) {
                        if (!f.startsWith('data:')) continue;
                        let evt;
                        try { evt = JSON.parse(f.slice(5).trim()); } catch (e) { continue; }
                        if (evt.type === 'sources') { ai.sources = evt.data; }
                        else if (evt.type === 'content') { ai.content += evt.data; this.scrollBottom(); }
                        else if (evt.type === 'done') { ai.streaming = false; await this.attachMsgIds(); }
                        else if (evt.type === 'error') { ai.content += '\n[出错] ' + evt.data; ai.streaming = false; }
                    }
                }
                ai.streaming = false;
                this.scrollBottom();
            } catch (e) {
                this.toastMsg('发送失败:' + e.message);
                const last = this.messages[this.messages.length - 1];
                if (last && last.role === 'assistant') { last.streaming = false; if (!last.content) last.content = '[请求失败]'; }
            }
            this.chatting = false;
        },
        async attachMsgIds() {
            // done后拉取会话消息,给本地消息补上数据库ID(反馈需要)
            if (!this.currentSession) return;
            try {
                const body = await this.api(`/api/chat/sessions/${this.currentSession}/messages`);
                const rows = (body.data && body.data.messages) || [];
                const assistantIds = rows.filter(m => m.role === 'assistant').map(m => m.id);
                let i = assistantIds.length - 1;
                for (let j = this.messages.length - 1; j >= 0 && i >= 0; j--) {
                    if (this.messages[j].role === 'assistant' && !this.messages[j].msgId) {
                        this.messages[j].msgId = assistantIds[i--];
                    }
                }
            } catch (e) { /* 忽略,反馈按钮不显示而已 */ }
        },
        async rate(idx, val) {
            const m = this.messages[idx];
            if (!m.msgId) { this.toastMsg('该消息暂不支持评价'); return; }
            try {
                // 再点同一评分 = 取消反馈;点另一个评分 = 改评分(后端upsert更新)
                if (m.rating === val) {
                    await this.api('/api/chat/feedback/' + m.msgId, { method: 'DELETE' });
                    m.rating = 0; this.toastMsg('已取消反馈');
                    return;
                }
                let reason = null;
                if (val === -1) reason = prompt('踩的原因(可选):') || null;
                await this.api('/api/chat/feedback', { method: 'POST', body: JSON.stringify({ message_id: m.msgId, rating: val, reason }) });
                m.rating = val; this.toastMsg('感谢反馈');
            } catch (e) { this.toastMsg('反馈失败'); }
        },
        scrollBottom() {
            this.$nextTick(() => {
                const box = this.$refs.msgsBox;
                if (box) box.scrollTop = box.scrollHeight;
            });
        },

        /* ===== 我的 ===== */
        initMine() {
            if (!this.user) { this.showLogin = true; return; }
            if (this.mineTab === 'fav' && !this.favList.length) this.loadFav();
            if (this.mineTab === 'history' && !this.historyList.length) this.loadHistory();
            if (this.mineTab === 'sources' && !this.sourceList.length) this.loadSources();
        },
        async loadFav() {
            try {
                const body = await this.api('/api/favorite/list?page=1&pageSize=50');
                this.favList = (body.data && (body.data.list || body.data.favorites || body.data)) || [];
            } catch (e) { console.warn(e); }
        },
        async loadHistory() {
            try {
                const body = await this.api('/api/history/list?page=1&pageSize=50');
                this.historyList = (body.data && (body.data.list || body.data.history || body.data)) || [];
            } catch (e) { console.warn(e); }
        },
        async loadSources() {
            try {
                const body = await this.api('/api/news/sources');
                this.sourceList = body.data || [];
                if (!this.srcForm.category_id && this.categories.length) this.srcForm.category_id = this.categories[0].id;
                else if (!this.categories.length) this.initHomeCats();
            } catch (e) { console.warn(e); }
        },
        async initHomeCats() {
            try {
                const body = await this.api('/api/news/categories');
                this.categories = (body.data || []).map(c => ({ id: c.id ?? c.category_id, name: c.name ?? c.category_name ?? c.title }));
                if (!this.srcForm.category_id && this.categories.length) this.srcForm.category_id = this.categories[0].id;
            } catch (e) { /* ignore */ }
        },
        async addSource() {
            const { name, url, category_id } = this.srcForm;
            if (!name || !url || !category_id) { this.toastMsg('请填写完整:名称/RSS地址/分类'); return; }
            try {
                const body = await this.api('/api/news/sources', { method: 'POST', body: JSON.stringify({ name, url, category_id }) });
                if (body.code !== 200) { this.toastMsg(body.message || '添加失败'); return; }
                this.srcForm.name = ''; this.srcForm.url = '';
                this.toastMsg('添加成功'); this.loadSources();
            } catch (e) { this.toastMsg('添加失败:' + e.message); }
        },
        async delSource(id) {
            if (!confirm('删除该新闻源?')) return;
            try { await this.api('/api/news/sources/' + id, { method: 'DELETE' }); this.toastMsg('已删除'); this.loadSources(); }
            catch (e) { this.toastMsg('删除失败'); }
        },
        async fetchSource(id) {
            this.toastMsg('抓取中,请稍候...');
            try {
                const body = await this.api(`/api/news/sources/${id}/fetch`, { method: 'POST' });
                if (body.code === 200) {
                    const d = body.data || {};
                    this.toastMsg(`抓取完成: 拉取${d.fetched}条, 新入库${d.inserted}条, 去重${d.skipped}条`, 3600);
                    this.loadSources();
                } else this.toastMsg(body.message || '抓取失败');
            } catch (e) { this.toastMsg('抓取失败:' + e.message); }
        },
    },
});

app.mount('#app');
