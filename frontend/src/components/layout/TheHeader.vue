<template>
  <header class="header glass">
    <div class="header-brand">
      <div class="brand-mark">MS</div>
      <div>
        <strong>MediaSpider</strong>
        <span>Intelligence Platform</span>
      </div>
    </div>
    <div class="header-actions">
      <div class="status-pill connected">
        <span class="status-dot"></span>
        <span>Backend Scaffold Ready</span>
      </div>
    </div>
  </header>
</template>

<style scoped>
.header {
  position: sticky;
  top: 0;
  z-index: 50;
  height: 72px;
  padding: 0 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  border-bottom: 1px solid rgba(226, 232, 240, 0.7);
}

.header-brand {
  display: flex;
  align-items: center;
  gap: 14px;
}

.brand-mark {
  width: 40px;
  height: 40px;
  display: grid;
  place-items: center;
  border-radius: 12px;
  background: linear-gradient(135deg, #3b82f6, #2563eb);
  color: #fff;
  font-size: 14px;
  font-weight: 800;
  box-shadow: 0 10px 22px rgba(59, 130, 246, 0.28);
}

.header-brand strong {
  display: block;
  font-size: 18px;
}

.header-brand span {
  color: #64748b;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.74);
  border: 1px solid rgba(226, 232, 240, 0.9);
  font-size: 13px;
  font-weight: 700;
}

.status-dot {
  width: 9px;
  height: 9px;
  border-radius: 999px;
  background: #10b981;
  box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.12);
}
</style>
