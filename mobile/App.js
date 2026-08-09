import { StatusBar } from 'expo-status-bar';
import React, { useEffect, useMemo, useState } from 'react';
import {
  Linking,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';

const API_BASE = process.env.EXPO_PUBLIC_API_URL || 'http://127.0.0.1:8000';
const tabs = ['Dashboard', 'Material Master', 'Stock In', 'Stock Out', 'Suppliers', 'Settings'];

const jsonHeaders = { 'Content-Type': 'application/json' };

async function api(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, options);
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || 'Request failed');
  }
  return res.json();
}

export default function App() {
  const [activeTab, setActiveTab] = useState('Dashboard');
  const [dashboard, setDashboard] = useState(null);
  const [materials, setMaterials] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [settings, setSettings] = useState(null);
  const [error, setError] = useState('');
  const [materialForm, setMaterialForm] = useState({ name: '', category: '', opening_stock: '0', minimum_stock: '0', unit_price: '0', unit: 'sheet', supplier_id: '' });
  const [stockInForm, setStockInForm] = useState({ material_id: '', quantity: '1' });
  const [stockOutForm, setStockOutForm] = useState({ material_id: '', quantity: '1' });
  const [supplierName, setSupplierName] = useState('');

  const materialMap = useMemo(() => new Map(materials.map((m) => [String(m.id), m.name])), [materials]);

  const refresh = async () => {
    setError('');
    try {
      const [d, m, s, cfg] = await Promise.all([
        api('/api/stock-management/dashboard'),
        api('/api/stock-management/materials'),
        api('/api/stock-management/suppliers'),
        api('/api/stock-management/settings'),
      ]);
      setDashboard(d);
      setMaterials(m);
      setSuppliers(s);
      setSettings(cfg);
    } catch (e) {
      setError(e.message);
    }
  };

  useEffect(() => { refresh(); }, []);

  const addMaterial = async () => {
    if (!materialForm.name || !materialForm.category) return setError('Name and category are required');
    await api('/api/stock-management/materials', {
      method: 'POST',
      headers: jsonHeaders,
      body: JSON.stringify({
        ...materialForm,
        opening_stock: Number(materialForm.opening_stock || 0),
        minimum_stock: Number(materialForm.minimum_stock || 0),
        unit_price: Number(materialForm.unit_price || 0),
        supplier_id: materialForm.supplier_id ? Number(materialForm.supplier_id) : null,
      }),
    });
    setMaterialForm({ name: '', category: '', opening_stock: '0', minimum_stock: '0', unit_price: '0', unit: 'sheet', supplier_id: '' });
    await refresh();
  };

  const addStockIn = async () => {
    if (!stockInForm.material_id) return setError('Select material for stock in');
    await api('/api/stock-management/stock-in', {
      method: 'POST',
      headers: jsonHeaders,
      body: JSON.stringify({ material_id: Number(stockInForm.material_id), quantity: Number(stockInForm.quantity || 0) }),
    });
    setStockInForm({ material_id: '', quantity: '1' });
    await refresh();
  };

  const addStockOut = async () => {
    if (!stockOutForm.material_id) return setError('Select material for stock out');
    await api('/api/stock-management/stock-out', {
      method: 'POST',
      headers: jsonHeaders,
      body: JSON.stringify({ material_id: Number(stockOutForm.material_id), quantity: Number(stockOutForm.quantity || 0) }),
    });
    setStockOutForm({ material_id: '', quantity: '1' });
    await refresh();
  };

  const addSupplier = async () => {
    if (!supplierName) return setError('Supplier name is required');
    await api('/api/stock-management/suppliers', {
      method: 'POST',
      headers: jsonHeaders,
      body: JSON.stringify({ name: supplierName }),
    });
    setSupplierName('');
    await refresh();
  };

  const saveSettings = async () => {
    await api('/api/stock-management/settings', {
      method: 'PUT',
      headers: jsonHeaders,
      body: JSON.stringify({ company_name: settings.company_name, currency: settings.currency, reorder_buffer: Number(settings.reorder_buffer || 1) }),
    });
    await refresh();
  };

  return (
    <View style={styles.container}>
      <StatusBar style="auto" />
      <Text style={styles.title}>Woodful Creations</Text>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.tabRow}>
        {tabs.map((tab) => (
          <TouchableOpacity key={tab} style={[styles.tab, activeTab === tab && styles.activeTab]} onPress={() => setActiveTab(tab)}>
            <Text style={activeTab === tab ? styles.activeTabText : styles.tabText}>{tab}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      {error ? <Text style={styles.error}>{error}</Text> : null}

      <ScrollView style={styles.body}>
        {activeTab === 'Dashboard' && dashboard ? (
          <>
            <Text style={styles.card}>Total Stock Value: ₹{Number(dashboard.total_stock_value).toFixed(2)}</Text>
            <Text style={styles.card}>Low Stock Items: {dashboard.low_stock_items}</Text>
            <Text style={styles.card}>Out of Stock: {dashboard.out_of_stock_items}</Text>
            <Text style={styles.card}>Purchase Value: ₹{Number(dashboard.purchase_value).toFixed(2)}</Text>
            <TouchableOpacity style={styles.button} onPress={() => Linking.openURL(`${API_BASE}/api/stock-management/reports/stock/download`)}>
              <Text style={styles.buttonText}>Open Excel Download</Text>
            </TouchableOpacity>
          </>
        ) : null}

        {activeTab === 'Material Master' ? (
          <>
            <TextInput style={styles.input} placeholder="Material name" value={materialForm.name} onChangeText={(v) => setMaterialForm({ ...materialForm, name: v })} />
            <TextInput style={styles.input} placeholder="Category" value={materialForm.category} onChangeText={(v) => setMaterialForm({ ...materialForm, category: v })} />
            <TextInput style={styles.input} placeholder="Opening stock" keyboardType="numeric" value={materialForm.opening_stock} onChangeText={(v) => setMaterialForm({ ...materialForm, opening_stock: v })} />
            <TextInput style={styles.input} placeholder="Minimum stock" keyboardType="numeric" value={materialForm.minimum_stock} onChangeText={(v) => setMaterialForm({ ...materialForm, minimum_stock: v })} />
            <TouchableOpacity style={styles.button} onPress={addMaterial}><Text style={styles.buttonText}>Add Material</Text></TouchableOpacity>
            {materials.map((m) => (
              <Text key={m.id} style={styles.listItem}>{m.name} | {m.category} | {m.current_stock} | {m.status}</Text>
            ))}
          </>
        ) : null}

        {activeTab === 'Stock In' ? (
          <>
            <TextInput style={styles.input} placeholder="Material ID" keyboardType="numeric" value={stockInForm.material_id} onChangeText={(v) => setStockInForm({ ...stockInForm, material_id: v })} />
            <TextInput style={styles.input} placeholder="Quantity" keyboardType="numeric" value={stockInForm.quantity} onChangeText={(v) => setStockInForm({ ...stockInForm, quantity: v })} />
            <TouchableOpacity style={styles.button} onPress={addStockIn}><Text style={styles.buttonText}>Add Purchase Entry</Text></TouchableOpacity>
            {materials.map((m) => <Text key={m.id} style={styles.listItem}>{m.id}: {m.name}</Text>)}
          </>
        ) : null}

        {activeTab === 'Stock Out' ? (
          <>
            <TextInput style={styles.input} placeholder="Material ID" keyboardType="numeric" value={stockOutForm.material_id} onChangeText={(v) => setStockOutForm({ ...stockOutForm, material_id: v })} />
            <TextInput style={styles.input} placeholder="Quantity" keyboardType="numeric" value={stockOutForm.quantity} onChangeText={(v) => setStockOutForm({ ...stockOutForm, quantity: v })} />
            <TouchableOpacity style={styles.button} onPress={addStockOut}><Text style={styles.buttonText}>Add Issue Entry</Text></TouchableOpacity>
            {materials.map((m) => <Text key={m.id} style={styles.listItem}>{m.id}: {m.name}</Text>)}
          </>
        ) : null}

        {activeTab === 'Suppliers' ? (
          <>
            <TextInput style={styles.input} placeholder="Supplier name" value={supplierName} onChangeText={setSupplierName} />
            <TouchableOpacity style={styles.button} onPress={addSupplier}><Text style={styles.buttonText}>Add Supplier</Text></TouchableOpacity>
            {suppliers.map((s) => <Text key={s.id} style={styles.listItem}>{s.name}</Text>)}
          </>
        ) : null}

        {activeTab === 'Settings' && settings ? (
          <>
            <TextInput style={styles.input} placeholder="Company name" value={settings.company_name} onChangeText={(v) => setSettings({ ...settings, company_name: v })} />
            <TextInput style={styles.input} placeholder="Currency" value={settings.currency} onChangeText={(v) => setSettings({ ...settings, currency: v })} />
            <TextInput style={styles.input} placeholder="Reorder buffer" keyboardType="numeric" value={String(settings.reorder_buffer)} onChangeText={(v) => setSettings({ ...settings, reorder_buffer: v })} />
            <TouchableOpacity style={styles.button} onPress={saveSettings}><Text style={styles.buttonText}>Save Settings</Text></TouchableOpacity>
          </>
        ) : null}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f3f5f8', paddingTop: 50, paddingHorizontal: 14 },
  title: { fontSize: 22, fontWeight: '700', marginBottom: 8 },
  tabRow: { maxHeight: 46, marginBottom: 8 },
  tab: { paddingHorizontal: 12, paddingVertical: 8, borderRadius: 20, borderWidth: 1, borderColor: '#aac2d5', marginRight: 8, backgroundColor: '#fff' },
  activeTab: { backgroundColor: '#1f4e78', borderColor: '#1f4e78' },
  tabText: { color: '#1f4e78' },
  activeTabText: { color: '#fff' },
  body: { flex: 1 },
  card: { backgroundColor: '#fff', padding: 12, borderRadius: 8, marginBottom: 8 },
  input: { backgroundColor: '#fff', borderRadius: 8, padding: 10, marginBottom: 8, borderWidth: 1, borderColor: '#d5dce4' },
  button: { backgroundColor: '#1f4e78', padding: 11, borderRadius: 8, alignItems: 'center', marginBottom: 10 },
  buttonText: { color: '#fff', fontWeight: '600' },
  listItem: { backgroundColor: '#fff', borderRadius: 6, padding: 8, marginBottom: 6 },
  error: { color: '#b00020', marginBottom: 8 },
});
