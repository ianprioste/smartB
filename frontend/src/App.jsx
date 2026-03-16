import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { ModelsPage, ColorsPage, TemplatesPage } from './pages/admin/AdminPages';
import { WizardNewPage } from './pages/wizard/WizardNew';
import { WizardPlainPage } from './pages/wizard/WizardPlain';
import { HomePage } from './pages/home/HomePage';
import { OrdersPage } from './pages/orders/OrdersPage';
import { ProductsListPage } from './pages/products/ProductsListPage';
import './styles/admin.css';

function App() {
  return (
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/products" element={<ProductsListPage />} />
        <Route path="/wizard/new" element={<WizardNewPage />} />
        <Route path="/wizard/plain" element={<WizardPlainPage />} />
        <Route path="/admin/models" element={<ModelsPage />} />
        <Route path="/admin/colors" element={<ColorsPage />} />
        <Route path="/admin/templates" element={<TemplatesPage />} />
        <Route path="/orders" element={<OrdersPage />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
