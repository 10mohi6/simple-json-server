document.addEventListener('DOMContentLoaded', () => {
    // --- Element References ---
    const resourceList = document.getElementById('resource-list');
    const currentResourceTitle = document.getElementById('current-resource-title');
    const queryInput = document.getElementById('query-input');
    const sendQueryBtn = document.getElementById('send-query-btn');
    const queryResult = document.querySelector('#query-result code');
    const tableTitle = document.getElementById('table-title');
    const dataTable = document.getElementById('data-table');
    const addItemBtn = document.getElementById('add-item-btn');
    
    // Item Modal
    const itemModal = new bootstrap.Modal(document.getElementById('form-modal'));
    const itemModalTitle = document.getElementById('modal-title');
    const jsonEditor = document.getElementById('json-editor');
    const saveItemBtn = document.getElementById('save-item-btn');
    const editItemId = document.getElementById('edit-item-id');

    // Resource Modal
    const manageResourcesBtn = document.getElementById('manage-resources-btn');
    const resourcesModal = new bootstrap.Modal(document.getElementById('resources-modal'));
    const resourceEditorContainer = document.getElementById('resource-editor-container');
    const newResourceNameInput = document.getElementById('new-resource-name');
    const addResourceBtn = document.getElementById('add-resource-btn');
    const saveResourcesBtn = document.getElementById('save-resources-btn');

    // --- State ---
    let currentResource = null;
    let currentData = [];
    let dbData = {}; // Holds the entire DB for resource management

    // --- Data Fetching and Rendering ---
    async function selectResource(resourceName) {
        if (!resourceName) {
            currentResource = null;
            currentData = [];
            renderTable([]);
            currentResourceTitle.textContent = 'Admin';
            tableTitle.textContent = 'Select a resource';
            queryInput.value = '';
            return;
        }
        currentResource = resourceName;
        currentResourceTitle.textContent = resourceName;
        tableTitle.textContent = resourceName;
        queryInput.value = resourceName;

        document.querySelectorAll('#resource-list .nav-link').forEach(link => {
            link.classList.toggle('active', link.dataset.resource === resourceName);
        });

        await fetchData(resourceName);
    }

    async function fetchData(resource) {
        try {
            const response = await fetch(`/${resource}`);
            if (!response.ok) throw new Error(`Failed to fetch data for ${resource}`);
            const data = await response.json();
            currentData = Array.isArray(data) ? data : [];
            renderTable(currentData);
        } catch (error) {
            console.error('Error fetching data:', error);
            alert(`Could not load data for ${resource}.`);
            renderTable([]);
        }
    }

    function renderTable(data) {
        const tableHead = dataTable.querySelector('thead');
        const tableBody = dataTable.querySelector('tbody');
        tableHead.innerHTML = '';
        tableBody.innerHTML = '';

        if (data.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="100%">No data available.</td></tr>';
            return;
        }

        const headers = Object.keys(data[0] || {});
        const headerRow = document.createElement('tr');
        headers.forEach(header => {
            const th = document.createElement('th');
            th.textContent = header;
            headerRow.appendChild(th);
        });
        headerRow.appendChild(document.createElement('th')).textContent = 'Actions';
        tableHead.appendChild(headerRow);

        data.forEach(item => {
            const row = document.createElement('tr');
            headers.forEach(header => {
                const td = document.createElement('td');
                let value = item[header];
                if (typeof value === 'object' && value !== null) {
                    td.innerHTML = `<pre><code>${JSON.stringify(value, null, 2)}</code></pre>`;
                } else {
                    td.textContent = value;
                }
                row.appendChild(td);
            });
            const actionsTd = document.createElement('td');
            actionsTd.innerHTML = `
                <button class="btn btn-sm btn-primary btn-edit" data-id="${item.id}">Edit</button>
                <button class="btn btn-sm btn-danger btn-delete" data-id="${item.id}">Delete</button>
            `;
            row.appendChild(actionsTd);
            tableBody.appendChild(row);
        });
    }

    // --- Initial Load ---
    async function loadResources() {
        try {
            const response = await fetch('/');
            if (!response.ok) throw new Error('Failed to fetch resources');
            const resources = await response.json();
            
            resourceList.innerHTML = '';
            if (resources.length === 0) {
                resourceList.innerHTML = '<li class="px-3 text-muted">No resources.</li>';
            }
            resources.forEach(resource => {
                const li = document.createElement('li');
                li.className = 'nav-item';
                li.innerHTML = `<a class="nav-link" href="#" data-resource="${resource}">${resource}</a>`;
                resourceList.appendChild(li);
            });

            selectResource(resources[0] || null);

        } catch (error) {
            console.error('Error loading resources:', error);
            alert('Could not load resources from the server.');
        }
    }

    // --- Query Handling ---
    async function handleQuery() {
        const query = queryInput.value;
        if (!query) {
            queryResult.textContent = 'Please enter a query.';
            return;
        }
        try {
            const response = await fetch(`/${query}`);
            const data = await response.json();
            const headers = Object.fromEntries(response.headers.entries());
            const resultText = `Status: ${response.status}\nHeaders: ${JSON.stringify(headers, null, 2)}\n\nBody: ${JSON.stringify(data, null, 2)}`;
            queryResult.textContent = resultText;

            const resourceFromQuery = query.split('?')[0].split('/')[0];
            if (resourceFromQuery === currentResource && Array.isArray(data)) {
                currentData = data;
                renderTable(data);
            }
        } catch (error) {
            console.error('Query error:', error);
            queryResult.textContent = `Error: ${error.message}`;
        }
    }

    // --- CRUD Handlers ---
    function handleAddItem() {
        if (!currentResource) {
            alert('Please select a resource first.');
            return;
        }
        editItemId.value = '';
        itemModalTitle.textContent = `Add New Item to ${currentResource}`;
        let template = (currentData && currentData.length > 0) 
            ? Object.keys(currentData[0]).reduce((acc, key) => ({ ...acc, [key]: '' }), {}) 
            : {};
        jsonEditor.value = JSON.stringify(template, null, 2);
        itemModal.show();
    }

    async function handleSaveItem() {
        const id = editItemId.value;
        let data;
        try {
            data = JSON.parse(jsonEditor.value);
        } catch (error) { return alert('Invalid JSON format.'); }

        const method = id ? 'PUT' : 'POST';
        const url = id ? `/${currentResource}/${id}` : `/${currentResource}`;

        try {
            const response = await fetch(url, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Save operation failed');
            }
            itemModal.hide();
            await selectResource(currentResource);
        } catch (error) {
            alert(`Error saving item: ${error.message}`);
        }
    }

    function handleTableActions(e) {
        const id = e.target.dataset.id;
        if (e.target.classList.contains('btn-edit')) handleEditItem(id);
        if (e.target.classList.contains('btn-delete')) handleDeleteItem(id);
    }

    function handleEditItem(id) {
        const itemToEdit = currentData.find(item => String(item.id) === String(id));
        if (!itemToEdit) return alert('Item not found.');
        
        editItemId.value = id;
        itemModalTitle.textContent = `Edit ${currentResource} #${id}`;
        jsonEditor.value = JSON.stringify(itemToEdit, null, 2);
        itemModal.show();
    }

    async function handleDeleteItem(id) {
        if (!confirm(`Are you sure you want to delete item #${id} from ${currentResource}?`)) return;

        try {
            const response = await fetch(`/${currentResource}/${id}`, { method: 'DELETE' });
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Delete operation failed');
            }
            await selectResource(currentResource);
        } catch (error) {
            alert(`Error deleting item: ${error.message}`);
        }
    }

    // --- Resource Management Handlers ---
    async function handleManageResources() {
        try {
            const response = await fetch('/_db');
            if (!response.ok) throw new Error('Could not fetch raw DB data.');
            dbData = await response.json();
            renderResourceEditor();
            resourcesModal.show();
        } catch (error) { alert(`Error: ${error.message}`); }
    }

    function renderResourceEditor() {
        resourceEditorContainer.innerHTML = '';
        Object.keys(dbData).forEach(key => {
            const div = document.createElement('div');
            div.className = 'input-group mb-2';
            div.innerHTML = `
                <input type="text" class="form-control resource-name-input" value="${key}" data-original-name="${key}">
                <button class="btn btn-outline-danger btn-delete-resource" data-name="${key}">Delete</button>
            `;
            resourceEditorContainer.appendChild(div);
        });
    }

    resourceEditorContainer.addEventListener('click', e => {
        if (e.target.classList.contains('btn-delete-resource')) {
            const resourceName = e.target.dataset.name;
            if (confirm(`Are you sure you want to delete the resource '${resourceName}' and all its data?`)) {
                e.target.closest('.input-group').remove();
            }
        }
    });

    function handleAddResource() {
        const newName = newResourceNameInput.value.trim();
        if (!newName || document.querySelector(`.resource-name-input[value="${newName}"]`)) {
            return alert('Invalid or duplicate resource name.');
        }
        const div = document.createElement('div');
        div.className = 'input-group mb-2';
        div.innerHTML = `
            <input type="text" class="form-control resource-name-input" value="${newName}" data-original-name="">
            <button class="btn btn-outline-danger btn-delete-resource" data-name="${newName}">Delete</button>
        `;
        resourceEditorContainer.appendChild(div);
        newResourceNameInput.value = '';
    }

    async function handleSaveResources() {
        const newDbData = {};
        const inputs = resourceEditorContainer.querySelectorAll('.resource-name-input');
        for (const input of inputs) {
            const originalName = input.dataset.originalName;
            const newName = input.value.trim();
            if (!newName) return alert('Resource name cannot be empty.');
            if (newDbData[newName]) return alert(`Duplicate resource name found: ${newName}`);
            newDbData[newName] = originalName ? dbData[originalName] : [];
        }

        try {
            const response = await fetch('/_db', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(newDbData) });
            if (!response.ok) throw new Error('Failed to save resources.');
            resourcesModal.hide();
            await loadResources();
        } catch (error) { alert(`Error: ${error.message}`); }
    }

    // --- Event Listeners ---
    resourceList.addEventListener('click', (e) => {
        if (e.target.tagName === 'A') {
            e.preventDefault();
            const resourceName = e.target.dataset.resource;
            selectResource(resourceName);
        }
    });
    sendQueryBtn.addEventListener('click', handleQuery);
    addItemBtn.addEventListener('click', handleAddItem);
    saveItemBtn.addEventListener('click', handleSaveItem);
    dataTable.addEventListener('click', handleTableActions);
    manageResourcesBtn.addEventListener('click', handleManageResources);
    addResourceBtn.addEventListener('click', handleAddResource);
    saveResourcesBtn.addEventListener('click', handleSaveResources);

    // --- Init ---
    loadResources();
});