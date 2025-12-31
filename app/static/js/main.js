/* main.js */
document.addEventListener('DOMContentLoaded', () => {
  'use strict';

  // Initialize Bootstrap Components
  const initBootstrap = () => {
    // Tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));

    // Popovers
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(popoverTriggerEl => new bootstrap.Popover(popoverTriggerEl));
  };

  // Sidebar Logic
  const initSidebar = () => {
    const sidebarLinks = document.querySelectorAll('.nav-icon-link');
    sidebarLinks.forEach(link => {
      link.addEventListener('click', function() {
        sidebarLinks.forEach(l => l.classList.remove('active'));
        this.classList.add('active');
      });
    });
  };

  // Tooth Chart Interactions
  const initToothChart = () => {
    const teeth = document.querySelectorAll('.tooth-item');
    teeth.forEach(tooth => {
      tooth.addEventListener('click', function() {
        // Toggle selection
        teeth.forEach(t => t.classList.remove('selected'));
        this.classList.add('selected');
        
        // Custom event for tooth selection
        const toothId = this.dataset.toothId;
        console.log(`Tooth ${toothId} selected`);
        
        // Trigger entrance animation for info panels
        const infoPanel = document.querySelector('.info-card-container');
        if(infoPanel) {
          infoPanel.classList.remove('animate-fade-in');
          void infoPanel.offsetWidth; // Trigger reflow
          infoPanel.classList.add('animate-fade-in');
        }
      });
    });
  };

  // Responsive Navbar Shadow on Scroll
  const initScrollEffects = () => {
    const header = document.querySelector('.top-header');
    if (header) {
      window.addEventListener('scroll', () => {
        if (window.scrollY > 10) {
          header.style.boxShadow = '0 2px 10px rgba(0,0,0,0.05)';
        } else {
          header.style.boxShadow = 'none';
        }
      });
    }
  };

  // Form Validation UI
  const initForms = () => {
    const forms = document.querySelectorAll('.needs-validation');
    Array.prototype.slice.call(forms).forEach(form => {
      form.addEventListener('submit', event => {
        if (!form.checkValidity()) {
          event.preventDefault();
          event.stopPropagation();
        }
        form.classList.add('was-validated');
      }, false);
    });
  };

  // Dark Mode Toggle Support
  const initDarkMode = () => {
    const toggle = document.querySelector('#dark-mode-toggle');
    if (toggle) {
      toggle.addEventListener('change', () => {
        document.body.classList.toggle('dark-mode');
      });
    }
  };

  // Execute all
  initBootstrap();
  initSidebar();
  initToothChart();
  initScrollEffects();
  initForms();
  initDarkMode();
});