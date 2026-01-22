import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ModelsPage, ColorsPage, TemplatesPage } from './pages/admin/AdminPages';
import './styles/admin.css';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/admin/models" element={<ModelsPage />} />
        <Route path="/admin/colors" element={<ColorsPage />} />
        <Route path="/admin/templates" element={<TemplatesPage />} />
        <Route path="/" element={<Navigate to="/admin/models" />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
