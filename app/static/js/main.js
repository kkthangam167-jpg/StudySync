// StudySync - Global Frontend Scripts

document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  initMobileNavigation();
  initGlobalSearch();
});

// Theme Management
function initTheme() {
  const themeToggleBtn = document.getElementById('theme-toggle-btn');
  const storedTheme = localStorage.getItem('studysync-theme') || 'dark';
  
  document.documentElement.setAttribute('data-theme', storedTheme);

  if (themeToggleBtn) {
    themeToggleBtn.addEventListener('click', async () => {
      const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
      const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
      
      document.documentElement.setAttribute('data-theme', newTheme);
      localStorage.setItem('studysync-theme', newTheme);

      // Persist to user profile if logged in
      try {
        await fetch('/api/theme', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ theme: newTheme })
        });
      } catch (e) {
        console.warn('Could not persist theme to server:', e);
      }
    });
  }
}

// Mobile Drawer Navigation
function initMobileNavigation() {
  const toggleBtn = document.getElementById('mobile-sidebar-toggle');
  const sidebar = document.querySelector('.app-sidebar');

  if (toggleBtn && sidebar) {
    toggleBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      sidebar.classList.toggle('open');
    });

    document.addEventListener('click', (e) => {
      if (!sidebar.contains(e.target) && !toggleBtn.contains(e.target)) {
        sidebar.classList.remove('open');
      }
    });
  }
}

// Universal Global Search
function initGlobalSearch() {
  const searchInput = document.getElementById('global-search-input');
  const resultsDropdown = document.getElementById('search-results-dropdown');

  if (!searchInput || !resultsDropdown) return;

  let debounceTimer;

  searchInput.addEventListener('input', () => {
    clearTimeout(debounceTimer);
    const query = searchInput.value.trim();

    if (query.length < 2) {
      resultsDropdown.style.display = 'none';
      resultsDropdown.innerHTML = '';
      return;
    }

    debounceTimer = setTimeout(async () => {
      try {
        const res = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
        const data = await res.json();
        
        if (data.results && data.results.length > 0) {
          resultsDropdown.innerHTML = data.results.map(r => `
            <a href="${r.url}" class="search-result-item" style="display: block; padding: 0.75rem 1rem; border-bottom: 1px solid var(--border-color); color: inherit; text-decoration: none;">
              <div style="display: flex; align-items: center; justify-content: space-between;">
                <span style="font-weight: 600; font-size: 0.88rem;">${r.title}</span>
                <span class="badge" style="background: rgba(99,102,241,0.2); color: #818cf8; font-size: 0.7rem;">${r.type}</span>
              </div>
              <div style="font-size: 0.76rem; color: var(--text-dim); margin-top: 2px;">${r.subtitle}</div>
            </a>
          `).join('');
          resultsDropdown.style.display = 'block';
        } else {
          resultsDropdown.innerHTML = `
            <div style="padding: 1rem; text-align: center; font-size: 0.85rem; color: var(--text-dim);">
              No matching academic records found.
            </div>
          `;
          resultsDropdown.style.display = 'block';
        }
      } catch (err) {
        console.error('Search error:', err);
      }
    }, 250);
  });

  document.addEventListener('click', (e) => {
    if (!searchInput.contains(e.target) && !resultsDropdown.contains(e.target)) {
      resultsDropdown.style.display = 'none';
    }
  });
}

// Modal Helper Functions
function openModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) {
    modal.style.display = 'flex';
  }
}

function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) {
    modal.style.display = 'none';
  }
}

// Close modal when clicking outside content
window.addEventListener('click', (e) => {
  if (e.target.classList.contains('modal-overlay')) {
    e.target.style.display = 'none';
  }
});
