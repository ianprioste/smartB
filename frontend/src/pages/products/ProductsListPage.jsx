import React, { useState, useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Layout } from '../../components/Layout';

const API_BASE = '/api';
const PRODUCTS_CACHE_KEY = 'smartb_products_catalog_v2';
const PRODUCTS_CACHE_SAVED_AT_KEY = 'smartb_products_catalog_saved_at_v2';

function groupProductsByParent(products) {
  if (!products || products.length === 0) return [];

  const parents = new Map();
  const variations = new Map();
  const orphans = [];

  for (const product of products) {
    if (product.pai === null || product.pai === undefined) {
      parents.set(product.id, product);
    } else {
      const parentId = product.pai;
      if (!variations.has(parentId)) {
        variations.set(parentId, []);
      }
      variations.get(parentId).push(product);
    }
  }

  for (const [parentId, children] of variations.entries()) {
    if (!parents.has(parentId)) {
      orphans.push(...children.map((child) => ({
        parent: child,
        children: [],
        expanded: false,
      })));
    }
  }

  const grouped = Array.from(parents.values()).map((parent) => ({
    parent,
    children: variations.get(parent.id) || [],
    expanded: false,
  }));

  return [...grouped, ...orphans];
}

function getProductTypeLabel(product, childrenCount = 0) {
  if (product.pai) return '📄 Variação';
  if (childrenCount > 0 || product.formato === 'V') return '📦 Produto pai';
  if (product.formato === 'E') return '🧩 Composição';
  return '◉ Simples';
}

function getStockTypeLabel(product) {
  const type = (product?.tipo_estoque || '').toUpperCase();
  if (type === 'V') return 'virtual';
  if (type === 'F') return 'físico';
  return 'não informado';
}

function getSubproductTypeLabel(product) {
  if (product?.formato === 'E') {
    return `🧩 Composição (${getStockTypeLabel(product)})`;
  }
  return '📄 Variação (físico)';
}

function productMatchesQuery(product, query) {
  const normalized = (query || '').trim().toLowerCase();
  if (!normalized) return true;

  const codigo = (product.codigo || '').toLowerCase();
  const nome = (product.nome || '').toLowerCase();
  const id = String(product.id || '').toLowerCase();

  return codigo.includes(normalized) || nome.includes(normalized) || id.includes(normalized);
}

function filterGroupedProducts(groups, query) {
  const normalized = (query || '').trim().toLowerCase();
  if (!normalized) return groups;

  return groups.filter((group) => {
    if (productMatchesQuery(group.parent, normalized)) {
      return true;
    }
    return group.children.some((child) => productMatchesQuery(child, normalized));
  });
}

function childHasPhysicalStock(product) {
  // Variations (formato !== 'E') are always physical
  if ((product.formato || '').toUpperCase() !== 'E') return true;
  // Compositions: only physical when tipoEstoque === 'F'
  return (product.tipo_estoque || '').toUpperCase() === 'F';
}

function filterGroupsWithPhysicalStock(groups) {
  return groups.filter((group) => group.children.some((child) => childHasPhysicalStock(child)));
}

export function ProductsListPage() {
  const [allProducts, setAllProducts] = useState([]);
  const [products, setProducts] = useState([]);
  const [groupedProducts, setGroupedProducts] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeQuery, setActiveQuery] = useState('');
  const [filterPhysical, setFilterPhysical] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [page, setPage] = useState(1);
  const [limit, setLimit] = useState(10);
  const [totalGroups, setTotalGroups] = useState(0);
  const [totalItems, setTotalItems] = useState(0);
  const [expandedGroups, setExpandedGroups] = useState(new Set());
  const [cacheSavedAt, setCacheSavedAt] = useState(null);
  const navigate = useNavigate();

  function loadProductsFromCache() {
    try {
      const raw = localStorage.getItem(PRODUCTS_CACHE_KEY);
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      if (!Array.isArray(parsed)) return null;
      return parsed;
    } catch (e) {
      return null;
    }
  }

  function saveProductsToCache(catalog) {
    try {
      localStorage.setItem(PRODUCTS_CACHE_KEY, JSON.stringify(catalog));
      const savedAt = new Date().toISOString();
      localStorage.setItem(PRODUCTS_CACHE_SAVED_AT_KEY, savedAt);
      setCacheSavedAt(savedAt);
    } catch (e) {
      // Ignore cache write failures and keep in-memory data.
    }
  }

  function loadCacheTimestamp() {
    const savedAt = localStorage.getItem(PRODUCTS_CACHE_SAVED_AT_KEY);
    setCacheSavedAt(savedAt || null);
  }

  const loadCatalog = useCallback(async (forceRefresh = false) => {
    try {
      if (!forceRefresh) {
        const cachedCatalog = loadProductsFromCache();
        if (cachedCatalog && cachedCatalog.length > 0) {
          setAllProducts(cachedCatalog);
          setError(null);
          setLoading(false);
          loadCacheTimestamp();
          return;
        }
      }

      setLoading(true);
      setError(null);

      const pageSize = 100;
      const firstParams = new URLSearchParams({ page: 1, limit: pageSize });
      const firstResp = await fetch(`${API_BASE}/bling/products/list/all?${firstParams}`);

      if (!firstResp.ok) {
        const err = await firstResp.json();
        const msg = err.detail?.message || 'Erro ao buscar produtos';
        setError(msg);
        setAllProducts([]);
        setProducts([]);
        setGroupedProducts([]);
      } else {
        const firstData = await firstResp.json();
        const firstItems = firstData.items || [];
        const totalCatalogPages = Math.ceil((firstData.total || 0) / pageSize);

        const restItems = [];
        if (totalCatalogPages > 1) {
          const pagePromises = [];
          for (let pageNum = 2; pageNum <= totalCatalogPages; pageNum += 1) {
            const params = new URLSearchParams({ page: pageNum, limit: pageSize });
            pagePromises.push(
              fetch(`${API_BASE}/bling/products/list/all?${params}`)
                .then(async (resp) => (resp.ok ? resp.json() : { items: [] }))
                .catch(() => ({ items: [] }))
            );
          }
          const pageResults = await Promise.all(pagePromises);
          pageResults.forEach((data) => {
            restItems.push(...(data.items || []));
          });
        }

        const dedupedById = new Map();
        [...firstItems, ...restItems].forEach((item) => dedupedById.set(item.id, item));
        const catalog = Array.from(dedupedById.values());

        setAllProducts(catalog);
        saveProductsToCache(catalog);
      }
    } catch (err) {
      setError(err.message);
      setAllProducts([]);
      setProducts([]);
      setGroupedProducts([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const applyLocalFilterAndPagination = useCallback(() => {
    const allGroups = groupProductsByParent(allProducts);
    let filteredGroups = filterGroupedProducts(allGroups, activeQuery);
    if (filterPhysical) {
      filteredGroups = filterGroupsWithPhysicalStock(filteredGroups);
    }

    const safeTotalPages = Math.max(1, Math.ceil(filteredGroups.length / limit));
    const safePage = Math.min(page, safeTotalPages);
    if (safePage !== page) {
      setPage(safePage);
      return;
    }

    const start = (safePage - 1) * limit;
    const end = start + limit;
    const pageGroups = filteredGroups.slice(start, end);
    const pageItems = pageGroups.flatMap((group) => [group.parent, ...group.children]);
    const filteredItemCount = filteredGroups.reduce((acc, group) => acc + 1 + group.children.length, 0);

    setGroupedProducts(pageGroups);
    setProducts(pageItems);
    setTotalGroups(filteredGroups.length);
    setTotalItems(filteredItemCount);

    if (pageItems.length === 0 && activeQuery) {
      setError(`Nenhum produto encontrado com "${activeQuery}"`);
    } else {
      setError(null);
    }
  }, [activeQuery, allProducts, filterPhysical, limit, page]);

  const handleSearch = useCallback((e) => {
    e.preventDefault();
    setExpandedGroups(new Set());
    const nextQuery = searchQuery.trim();
    if (nextQuery === activeQuery) return;
    setPage(1);
    setActiveQuery(nextQuery);
  }, [activeQuery, searchQuery]);

  const toggleGroup = useCallback((parentId) => {
    setExpandedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(parentId)) {
        next.delete(parentId);
      } else {
        next.add(parentId);
      }
      return next;
    });
  }, []);

  const handlePageChange = useCallback((newPage) => {
    setExpandedGroups(new Set());
    setPage(newPage);
  }, []);

  useEffect(() => {
    loadCatalog();
  }, [loadCatalog]);

  useEffect(() => {
    setExpandedGroups(new Set());
    setPage(1);
  }, [limit]);

  useEffect(() => {
    setExpandedGroups(new Set());
    applyLocalFilterAndPagination();
  }, [applyLocalFilterAndPagination]);

  const totalPages = Math.ceil(totalGroups / limit);

  return (
    <Layout>
      <div className="page-inner">
        <div className="page-header">
          <div>
            <h2>Produtos</h2>
            <p className="page-subtitle">Catálogo completo de produtos</p>
            {cacheSavedAt && (
              <p className="page-subtitle" style={{ fontSize: 12 }}>
                Cache local atualizado em {new Date(cacheSavedAt).toLocaleString('pt-BR')}
              </p>
            )}
          </div>
          <button
            className="btn-secondary"
            onClick={() => {
              setExpandedGroups(new Set());
              setPage(1);
              loadCatalog(true);
            }}
            disabled={loading}
          >
            {loading ? 'Atualizando...' : 'Atualizar do Bling'}
          </button>
        </div>

        {error && <div className="error">{error}</div>}

        {/* Search Box */}
        <div className="card" style={{ marginBottom: 24 }}>
          <div className="card-header">
            <h3>🔍 Filtrar Produtos</h3>
          </div>
          <form onSubmit={handleSearch} style={{ padding: '20px' }}>
            <div className="search-box">
              <input
                type="text"
                placeholder="Digite o nome ou SKU do produto (opcional)…"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                disabled={loading}
              />
              <button type="submit" disabled={loading}>
                {loading ? 'Buscando…' : '🔍 Filtrar'}
              </button>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginTop: 12, flexWrap: 'wrap' }}>
              <p style={{ fontSize: 12, color: '#94a3b8', margin: 0 }}>
                Deixe em branco para ver todos os produtos • Busca por nome/SKU/ID sem diferenciar maiúsculas e minúsculas
              </p>
              <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: '#475569', cursor: 'pointer', userSelect: 'none', whiteSpace: 'nowrap' }}>
                <input
                  type="checkbox"
                  checked={filterPhysical}
                  onChange={(e) => { setFilterPhysical(e.target.checked); setPage(1); setExpandedGroups(new Set()); }}
                  disabled={loading}
                />
                📦 Apenas estoque físico
              </label>
            </div>
          </form>
        </div>

        {/* Results */}
        <div className="card">
          <div className="card-header">
            <h3>
              📦 Produtos
              {totalItems > 0 && (
                <span style={{ fontSize: 12, color: '#64748b', fontWeight: 'normal', marginLeft: 8 }}>
                  ({totalItems} produto{totalItems !== 1 ? 's' : ''} em {totalGroups} grupo{totalGroups !== 1 ? 's' : ''})
                </span>
              )}
            </h3>
          </div>

          {!loading && groupedProducts.length > 0 && (
            <div style={{ padding: '12px 20px 0', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
              <p style={{ color: '#64748b', fontSize: 13, margin: 0 }}>
                Exibindo {groupedProducts.length} grupo{groupedProducts.length !== 1 ? 's' : ''} nesta página
              </p>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#475569', fontSize: 13 }}>
                Grupos por página
                <select value={limit} onChange={(e) => setLimit(Number(e.target.value))} disabled={loading}>
                  <option value={10}>10</option>
                  <option value={20}>20</option>
                  <option value={30}>30</option>
                </select>
              </label>
            </div>
          )}

          {loading && <p className="loading">Carregando produtos…</p>}

          {!loading && products.length === 0 && (
            <div className="empty-state" style={{ padding: '60px 20px' }}>
              <span className="empty-state-icon">📭</span>
              <p>
                {searchQuery.trim()
                  ? `Nenhum produto encontrado com "${searchQuery}"`
                  : 'Nenhum produto disponível'}
              </p>
            </div>
          )}

          {!loading && products.length > 0 && (
            <>
              <div style={{ overflowX: 'auto' }}>
                <table className="table">
                  <thead>
                    <tr>
                      <th style={{ width: '35%' }}>Nome do Produto</th>
                      <th style={{ width: '25%' }}>SKU</th>
                      <th style={{ width: '25%' }}>Tipo</th>
                      <th style={{ width: '12%' }}></th>
                    </tr>
                  </thead>
                  <tbody>
                    {groupedProducts.map((group) => (
                      <React.Fragment key={group.parent.id}>
                        <tr
                          style={{
                            background: group.children.length > 0 ? '#f8fafc' : 'transparent',
                            cursor: group.children.length > 0 ? 'pointer' : 'default',
                          }}
                          onClick={() => group.children.length > 0 && toggleGroup(group.parent.id)}
                        >
                          <td style={{ fontWeight: 500 }}>
                            {group.children.length > 0 && (
                              <span
                                style={{
                                  display: 'inline-block',
                                  marginRight: 8,
                                  fontSize: 12,
                                  transform: expandedGroups.has(group.parent.id)
                                    ? 'rotate(90deg)'
                                    : 'rotate(0)',
                                  transition: 'transform 0.2s',
                                }}
                              >
                                ›
                              </span>
                            )}
                            {group.parent.nome}
                          </td>
                          <td>
                            <code style={{ background: '#f1f5f9', padding: '3px 8px', borderRadius: 4, fontSize: 12 }}>
                              {group.parent.codigo}
                            </code>
                          </td>
                          <td style={{ fontSize: 12 }}>
                            {getProductTypeLabel(group.parent, group.children.length)}
                          </td>
                          <td onClick={(e) => e.stopPropagation()}>
                            <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                              <button
                                onClick={() => navigate('/wizard/new', { state: { editProduct: group.parent } })}
                                style={{
                                  padding: '4px 10px',
                                  fontSize: 12,
                                  background: '#3b82f6',
                                  color: '#fff',
                                  border: 'none',
                                  borderRadius: 6,
                                  cursor: 'pointer',
                                  whiteSpace: 'nowrap',
                                }}
                                title="Abrir Wizard de estampados"
                              >
                                🪄 Wizard
                              </button>
                              <button
                                onClick={() => navigate('/wizard/plain', { state: { editProduct: group.parent } })}
                                style={{
                                  padding: '4px 10px',
                                  fontSize: 12,
                                  background: '#0f766e',
                                  color: '#fff',
                                  border: 'none',
                                  borderRadius: 6,
                                  cursor: 'pointer',
                                  whiteSpace: 'nowrap',
                                }}
                                title="Abrir Wizard de produto liso"
                              >
                                🧩 Wizard Liso
                              </button>
                            </div>
                          </td>
                        </tr>

                        {expandedGroups.has(group.parent.id) &&
                          group.children.length > 0 &&
                          group.children.map((child) => (
                            <tr
                              key={child.id}
                              style={{
                                background: '#fafbfc',
                                borderLeft: '3px solid #3b82f6',
                              }}
                            >
                              <td style={{ paddingLeft: '40px', fontWeight: 400, color: '#334155', fontSize: 13 }}>
                                └ {child.nome}
                              </td>
                              <td>
                                <code style={{ background: '#e0f2fe', padding: '3px 8px', borderRadius: 4, fontSize: 11 }}>
                                  {child.codigo}
                                </code>
                              </td>
                              <td style={{ fontSize: 12 }}>{getSubproductTypeLabel(child)}</td>
                              <td />
                            </tr>
                          ))}
                      </React.Fragment>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div style={{ padding: '16px 20px', borderTop: '1px solid #f1f5f9', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <p style={{ color: '#64748b', fontSize: 13, margin: 0 }}>
                    Página {page} de {totalPages}
                  </p>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button
                      onClick={() => handlePageChange(page - 1)}
                      disabled={page === 1 || loading}
                      style={{ padding: '8px 12px', fontSize: 13 }}
                    >
                      ← Anterior
                    </button>
                    <button
                      onClick={() => handlePageChange(page + 1)}
                      disabled={page === totalPages || loading}
                      style={{ padding: '8px 12px', fontSize: 13 }}
                    >
                      Próxima →
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </Layout>
  );
}

