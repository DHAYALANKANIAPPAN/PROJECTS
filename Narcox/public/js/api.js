// public/js/api.js

// A tool to safely display text so hackers can't inject bad code
const esc = (s) => {
    const el = document.createElement('div');
    el.innerText = s;
    return el.innerHTML;
};

// A tool to generate a colored badge based on the risk score (0-10)
const riskBadge = (risk) => {
    if (risk >= 7) return `<span class="px-2 py-1 whitespace-nowrap bg-red-100 text-red-800 border border-red-200 rounded-full text-xs font-medium">High (${risk})</span>`;
    if (risk >= 4) return `<span class="px-2 py-1 whitespace-nowrap bg-orange-100 text-orange-800 border border-orange-200 rounded-full text-xs font-medium">Medium (${risk})</span>`;
    return `<span class="px-2 py-1 whitespace-nowrap bg-green-100 text-green-800 border border-green-200 rounded-full text-xs font-medium">Low (${risk})</span>`;
};

// A tool that runs a function immediately, and then again every 5 seconds
const poll = (fn, ms = 5000) => {
    fn();
    setInterval(fn, ms);
};

// The API tool to fetch data from the server
const API = {
    async get(path) {
        try {
            const res = await fetch(path);
            if (!res.ok) throw new Error('API Error');
            return await res.json();
        } catch (e) {
            console.error('Fetch failed, falling back to mock data for:', path);
            // If the real API fails, we fetch our fake dummy data instead!
            const mockRes = await fetch('/js/mock.json');
            const mockData = await mockRes.json();
            return mockData[path] || null;
        }
    },
    async post(path, body) {
        const res = await fetch(path, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        return await res.json();
    }
};
