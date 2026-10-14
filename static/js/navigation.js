/* Links remain visible when JavaScript is unavailable. */
(() => {
  const toggle = document.querySelector('[data-navigation-toggle]');
  const navigation = document.getElementById('mesa-navigation');
  if (!toggle || !navigation) return;
  const mobile = window.matchMedia('(max-width: 991.98px)');
  const update = () => {
    toggle.hidden = !mobile.matches;
    navigation.hidden = mobile.matches;
    toggle.setAttribute('aria-expanded', String(!navigation.hidden));
  };
  toggle.addEventListener('click', () => {
    navigation.hidden = !navigation.hidden;
    toggle.setAttribute('aria-expanded', String(!navigation.hidden));
  });
  navigation.addEventListener('keydown', event => {
    if (event.key === 'Escape' && mobile.matches) {
      navigation.hidden = true;
      toggle.setAttribute('aria-expanded', 'false');
      toggle.focus();
    }
  });
  mobile.addEventListener('change', update);
  update();
})();
