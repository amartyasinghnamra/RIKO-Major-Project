import './styles.css';

const menuToggle = document.querySelector<HTMLButtonElement>('.menu-toggle');
const primaryNav = document.querySelector<HTMLElement>('#primary-nav');

menuToggle?.addEventListener('click', () => {
  const isOpen = primaryNav?.classList.toggle('open') ?? false;
  menuToggle.setAttribute('aria-expanded', String(isOpen));
});

primaryNav?.querySelectorAll('a').forEach(link => {
  link.addEventListener('click', () => {
    primaryNav.classList.remove('open');
    menuToggle?.setAttribute('aria-expanded', 'false');
  });
});

document.querySelectorAll<HTMLButtonElement>('.copy-code').forEach(button => {
  button.addEventListener('click', async () => {
    const targetId = button.dataset.copy;
    const code = targetId
      ? document.querySelector<HTMLElement>(`#${targetId} code`)
      : null;
    if (!code) return;
    try {
      await navigator.clipboard.writeText(code.innerText);
      const original = button.textContent;
      button.textContent = 'Copied';
      window.setTimeout(() => {
        button.textContent = original ?? 'Copy';
      }, 1400);
    } catch {
      button.textContent = 'Select text';
    }
  });
});
