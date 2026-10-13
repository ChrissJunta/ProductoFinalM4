// Ayuda de presentación; el backend vuelve a validar categoría y subcategoría.
(() => {
  const category = document.getElementById('id_category');
  const subcategory = document.getElementById('id_subcategory');
  const data = document.getElementById('category-tree');
  if (!category || !subcategory || !data) return;
  const tree = JSON.parse(data.textContent);
  const options = Array.from(subcategory.options, option => option.cloneNode(true));
  const filter = (keepInvalidSelection) => {
    const selected = subcategory.value;
    const item = tree.find(entry => String(entry.id) === category.value);
    const allowed = new Set((item?.subcategories || []).map(entry => String(entry.id)));
    subcategory.replaceChildren(...options.filter(option => !category.value || !option.value || allowed.has(option.value) || (keepInvalidSelection && option.value === selected)).map(option => option.cloneNode(true)));
    subcategory.value = Array.from(subcategory.options).some(option => option.value === selected) ? selected : '';
  };
  // Conserva valores de un POST inválido para poder corregir el error del servidor.
  filter(true);
  category.addEventListener('change', () => filter(false));
})();
