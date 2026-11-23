const icon = (name) => {
  const paths = {
    dashboard: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/><rect x="14" y="11" width="7" height="10" rx="1"/><rect x="3" y="13" width="7" height="8" rx="1"/>',
    products: '<path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="m3 12 9 5 9-5M3 16l9 5 9-5M12 8v5"/>',
    categories: '<rect x="3" y="3" width="8" height="8" rx="1.5"/><rect x="13" y="3" width="8" height="8" rx="1.5"/><rect x="3" y="13" width="8" height="8" rx="1.5"/><rect x="13" y="13" width="8" height="8" rx="1.5"/>',
    enquiries: '<path d="M4 5h16v12H8l-4 3V5Z"/><path d="M8 9h8m-8 4h5"/>',
    quotes: '<path d="M6 3h9l4 4v14H6z"/><path d="M14 3v5h5M9 13h7m-7 4h7"/>',
    customers: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0m2-11a3.5 3.5 0 0 1 0 6m1.5 1a5 5 0 0 1 2.5 4"/>',
    service: '<path d="M14.5 6.5a5 5 0 0 0-6.8 6.8L3 18l3 3 4.7-4.7a5 5 0 0 0 6.8-6.8L14 14l-4-4 4.5-3.5Z"/>',
    equipment: '<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M9 7h6m-6 4h6m-6 4h3"/>',
    manuals: '<path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v16H6.5A2.5 2.5 0 0 0 4 21z"/><path d="M4 5.5v13A2.5 2.5 0 0 1 6.5 16H20M8 7h8m-8 3h8"/>',
    content: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 9h10m-10 4h7"/>',
    knowledge: '<circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.5 2.5 0 1 1 4.6 1.3c-.8 1.1-2.1 1.3-2.1 3.2m0 3h.01"/>',
    notifications: '<path d="M18 9a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/>',
    users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0m3-12h4m-2-2v4"/>',
    settings: '<circle cx="12" cy="12" r="3"/><path d="m19.4 15 .1.1 1.4 1.1-1.4 2.4-1.7-.7a8 8 0 0 1-1.8 1l-.3 1.8h-2.8l-.3-1.8a8 8 0 0 1-1.8-1l-1.7.7-1.4-2.4 1.4-1.1a7 7 0 0 1 0-2l-1.4-1.1 1.4-2.4 1.7.7a8 8 0 0 1 1.8-1l.3-1.8h2.8l.3 1.8a8 8 0 0 1 1.8 1l1.7-.7 1.4 2.4-1.4 1.1a7 7 0 0 1 0 2Z"/>',
    audit: '<path d="M4 5h16M4 10h16M4 15h10M4 20h7"/><circle cx="18" cy="18" r="3"/>'
  };
  return `<svg viewBox="0 0 24 24" aria-hidden="true">${paths[name] || paths.dashboard}</svg>`;
};

const sections = [
  { title: 'OVERVIEW', items: [['Dashboard','dashboard']] },
  { title: 'SALES & CONTENT', items: [['Products','products'],['Categories','categories'],['Enquiries','enquiries'],['Quotations','quotes'],['Customers','customers']] },
  { title: 'SERVICE', items: [['Service requests','service'],['Equipment','equipment'],['Manuals & documents','manuals']] },
  { title: 'PLATFORM', items: [['App content','content'],['FAQs & knowledge','knowledge'],['Notifications','notifications'],['Users & roles','users'],['Settings','settings'],['Audit log','audit']] }
];

const nav = document.querySelector('#navigation');
sections.forEach((section, sectionIndex) => {
  if (sectionIndex) nav.insertAdjacentHTML('beforeend', `<li class="nav-section">${section.title}</li>`);
  section.items.forEach(([label, key]) => nav.insertAdjacentHTML('beforeend', `<li><a href="#${key}" data-page="${key}" class="${key === 'dashboard' ? 'active' : ''}">${icon(key)}<span>${label}</span></a></li>`));
});

const metrics = [
  ['New enquiries','enquiries','New and unassigned'],
  ['Quotations pending','quotes','Awaiting preparation'],
  ['Open service tickets','service','Across all statuses'],
  ['Customers','customers','Customer accounts']
];

function heading(kicker, title, description, actions = '') {
  return `<div class="page-heading"><div><p class="eyebrow">${kicker}</p><h1>${title}</h1><p>${description}</p></div>${actions ? `<div class="page-actions">${actions}</div>` : ''}</div>`;
}

function emptyState(symbol, title, text) {
  return `<div class="empty-state"><div><div class="empty-icon">${icon(symbol)}</div><h3>${title}</h3><p>${text}</p></div></div>`;
}

function dashboard() {
  return `${heading('Monday, November 23, 2026','Good morning','Here’s your platform workspace. Live operational data will appear once the backend is connected.')}
    <section class="metrics-grid" aria-label="Operational metrics">${metrics.map(([label, symbol, foot]) => `<article class="card metric-card"><div class="card-body"><div class="metric-top"><span class="metric-label">${label}</span><span class="metric-icon">${icon(symbol)}</span></div><div class="metric-value" aria-label="Not connected">—</div><div class="metric-foot">${foot} · not connected</div></div></article>`).join('')}</section>
    <section class="section-grid"><article class="card panel"><header class="panel-head"><div><h2>Recent enquiries</h2><p>Latest customer requests and RFQs</p></div><button class="btn btn-ghost btn-sm" data-page="enquiries">View queue <span aria-hidden="true">→</span></button></header>${emptyState('enquiries','No enquiry data yet','Connect the API and authorized CRM source to see customer requests here.')}</article>
    <article class="card panel"><header class="panel-head"><div><h2>Action required</h2><p>Work that needs a team response</p></div></header><div class="queue-list"><div class="queue-row"><i class="queue-dot"></i><div><strong>Enquiries needing assignment</strong><span>Available when the enquiries workflow is connected</span></div><span class="queue-count">—</span></div><div class="queue-row"><i class="queue-dot"></i><div><strong>Quotations to prepare</strong><span>Available when quote records are connected</span></div><span class="queue-count">—</span></div><div class="queue-row"><i class="queue-dot"></i><div><strong>Urgent service requests</strong><span>Available when ticket records are connected</span></div><span class="queue-count">—</span></div></div></article></section>
    <article class="card panel table-panel"><header class="panel-head"><div><h2>Service queue</h2><p>Open customer service requests</p></div><button class="btn btn-ghost btn-sm" data-page="service">View service <span aria-hidden="true">→</span></button></header>${emptyState('service','No service records connected','Ticket rows will appear here after API, permissions, and service ownership are configured.')}</article>`;
}

function products() {
  const actions = `<button class="btn btn-outline" id="export-disabled" disabled title="Export becomes available when product records are connected">Export</button><button class="btn btn-primary" id="add-product" title="Product editing is not connected yet">${icon('products')} Add product</button>`;
  return `${heading('CATALOGUE','Products','Manage verified models, technical specifications, and published documents.',actions)}
    <article class="card panel table-panel"><div class="table-toolbar"><label class="input input-bordered"><span class="sr-only">Search products</span>${icon('dashboard')}<input id="product-search" type="search" placeholder="Search by product or model" aria-label="Search products" /></label><select class="select select-bordered" aria-label="Filter by publishing status" disabled><option>All statuses</option></select><span class="text-xs text-base-content/55">No records loaded</span></div>
    <div class="overflow-x-auto"><table class="table table-sm content-table"><thead><tr><th>Product</th><th>Category</th><th>Model</th><th>Status</th><th>Updated</th><th><span class="sr-only">Actions</span></th></tr></thead><tbody><tr><td colspan="6">${emptyState('products','Your catalogue is empty','No product records were supplied. Connect the authorized catalogue source before adding or publishing product claims.')}</td></tr></tbody></table></div>
    <footer class="panel-head"><span class="text-xs text-base-content/55">Showing 0 products</span><div class="join"><button class="btn btn-sm join-item" disabled aria-label="Previous page">‹</button><button class="btn btn-sm join-item" disabled aria-label="Next page">›</button></div></footer></article>
    <div class="module-card mt-4"><span class="metric-icon">${icon('knowledge')}</span><div><strong>Verified content only</strong><p>Specifications and documents must come from approved EnerTech sources before publishing.</p></div><span class="badge badge-outline">Content policy</span></div>`;
}

const moduleMeta = {
  categories: ['Categories','Organize catalogue categories and validated attribute schemas.'],
  enquiries: ['Enquiries','Review, assign, and track customer RFQs when connected to the approved source.'],
  quotes: ['Quotations','Manage quotation revisions and customer visibility from approved quote records.'],
  customers: ['Customers','View customer records and history according to granted permissions.'],
  service: ['Service requests','Triage tickets, severity, customer updates, and resolution history.'],
  equipment: ['Equipment','Review registrations and verified equipment records.'],
  manuals: ['Manuals & documents','Manage approved documents, versions, languages, and access.'],
  content: ['App content','Preview and publish supported customer-facing homepage sections.'],
  knowledge: ['FAQs & knowledge','Manage reviewed, approved content for customer support.'],
  notifications: ['Notifications','Manage templates and consent-aware delivery workflows.'],
  users: ['Users & roles','Apply least-privilege access and review privileged account actions.'],
  settings: ['Settings','Configure confirmed platform policies and customer-facing settings.'],
  audit: ['Audit log','Review sensitive changes after audit storage is connected.']
};

function modulePage(key) {
  const [title, desc] = moduleMeta[key];
  return `${heading('WORKSPACE',title,desc)}<article class="card panel">${emptyState(key,'This module is not connected yet','This prototype contains no live records or write actions. The API, role policy, and workflow must be implemented before this module can change customer data.')}</article>`;
}

function render(page = 'dashboard') {
  const main = document.querySelector('#page-content');
  const active = document.querySelector(`[data-page="${page}"]`);
  const title = active?.querySelector('span')?.textContent || 'Dashboard';
  document.querySelector('#crumb').textContent = title;
  document.title = `EnerTech Admin · ${title}`;
  document.querySelectorAll('#navigation [data-page]').forEach((item) => item.classList.toggle('active', item.dataset.page === page));
  main.innerHTML = page === 'dashboard' ? dashboard() : page === 'products' ? products() : modulePage(page);
  main.querySelectorAll('[data-page]').forEach((button) => button.addEventListener('click', (event) => {
    event.preventDefault();
    const target = button.dataset.page;
    history.pushState({ page: target }, '', `#${target}`);
    render(target);
  }));
  const mobileDrawer = document.querySelector('#admin-drawer');
  main.querySelectorAll('button[data-page]').forEach((button) => button.addEventListener('click', () => { mobileDrawer.checked = false; }));
}

document.querySelectorAll('#navigation [data-page]').forEach((link) => link.addEventListener('click', (event) => {
  event.preventDefault();
  history.pushState({ page: link.dataset.page }, '', `#${link.dataset.page}`);
  render(link.dataset.page);
  document.querySelector('#admin-drawer').checked = false;
}));
window.addEventListener('popstate', () => render(location.hash.slice(1) || 'dashboard'));
render(location.hash.slice(1) || 'dashboard');
