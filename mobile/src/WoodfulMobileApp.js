import AsyncStorage from "@react-native-async-storage/async-storage";
import { StatusBar } from "expo-status-bar";
import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  RefreshControl,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import {
  createMobileApi,
  getDefaultApiBaseUrl,
  normalizeApiBaseUrl,
} from "./api";

const STORAGE_KEYS = {
  apiUrl: "woodful.mobile.apiUrl",
  conversationId: "woodful.mobile.conversationId",
  token: "woodful.mobile.token",
  user: "woodful.mobile.user",
};

const TAB_ITEMS = [
  { key: "dashboard", label: "Dashboard" },
  { key: "inventory", label: "Inventory" },
  { key: "clients", label: "Clients" },
  { key: "payments", label: "Payments" },
  { key: "chat", label: "Chat" },
  { key: "modules", label: "More" },
];

const INVENTORY_FORM_DEFAULTS = {
  material_type: "",
  thickness: "",
  category: "",
  description: "",
  quantity: "",
  min_quantity: "10",
  price_per_unit: "",
  unit: "sheets",
  sku: "",
  supplier: "",
};

const CLIENT_FORM_DEFAULTS = {
  name: "",
  email: "",
  phone: "",
  company: "",
  address: "",
};

const PAYMENT_FORM_DEFAULTS = {
  payment_type: "supplier",
  related_id: "",
  amount: "",
  payment_method: "bank_transfer",
  description: "",
};

function formatCurrency(value) {
  const amount = Number(value) || 0;
  return `Rs ${amount.toLocaleString("en-IN", {
    maximumFractionDigits: 2,
  })}`;
}

function formatDate(value) {
  if (!value) {
    return "Not available";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString();
}

function getDisplayName(user) {
  return user?.full_name || user?.username || user?.email || "User";
}

function StatCard({ label, value, tone = "default" }) {
  return (
    <View
      style={[styles.statCard, tone === "warning" && styles.statCardWarning]}
    >
      <Text style={styles.statLabel}>{label}</Text>
      <Text style={styles.statValue}>{value}</Text>
    </View>
  );
}

function SectionCard({ title, subtitle, children, action }) {
  return (
    <View style={styles.sectionCard}>
      <View style={styles.sectionHeader}>
        <View style={styles.sectionHeaderText}>
          <Text style={styles.sectionTitle}>{title}</Text>
          {subtitle ? (
            <Text style={styles.sectionSubtitle}>{subtitle}</Text>
          ) : null}
        </View>
        {action}
      </View>
      {children}
    </View>
  );
}

function EmptyState({ title, description }) {
  return (
    <View style={styles.emptyState}>
      <Text style={styles.emptyStateTitle}>{title}</Text>
      <Text style={styles.emptyStateText}>{description}</Text>
    </View>
  );
}

function PrimaryButton({
  title,
  onPress,
  disabled,
  tone = "primary",
  fullWidth = false,
}) {
  return (
    <Pressable
      style={[
        styles.button,
        fullWidth && styles.fullWidthButton,
        tone === "secondary" && styles.secondaryButton,
        disabled && styles.disabledButton,
      ]}
      onPress={onPress}
      disabled={disabled}
    >
      <Text
        style={[
          styles.buttonText,
          tone === "secondary" && styles.secondaryButtonText,
        ]}
      >
        {title}
      </Text>
    </Pressable>
  );
}

function TextField({
  label,
  value,
  onChangeText,
  placeholder,
  keyboardType,
  autoCapitalize = "sentences",
  secureTextEntry = false,
  multiline = false,
}) {
  return (
    <View style={styles.fieldGroup}>
      <Text style={styles.fieldLabel}>{label}</Text>
      <TextInput
        style={[styles.input, multiline && styles.multilineInput]}
        value={value}
        onChangeText={onChangeText}
        placeholder={placeholder}
        placeholderTextColor="#8d8179"
        keyboardType={keyboardType}
        autoCapitalize={autoCapitalize}
        secureTextEntry={secureTextEntry}
        multiline={multiline}
      />
    </View>
  );
}

function Chip({ label, selected, onPress }) {
  return (
    <Pressable
      style={[styles.chip, selected && styles.chipSelected]}
      onPress={onPress}
    >
      <Text style={[styles.chipText, selected && styles.chipTextSelected]}>
        {label}
      </Text>
    </Pressable>
  );
}

function LoginScreen({
  apiBaseUrl,
  initialConnectionMessage,
  onLogin,
  onTestConnection,
  testingConnection,
}) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [serverUrl, setServerUrl] = useState(apiBaseUrl);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setServerUrl(apiBaseUrl);
  }, [apiBaseUrl]);

  const handleSubmit = async () => {
    setLoading(true);
    setError("");

    try {
      await onLogin({
        email,
        password,
        serverUrl,
      });
    } catch (loginError) {
      setError(loginError.message);
    } finally {
      setLoading(false);
    }
  };

  const handleConnectionTest = async () => {
    setError("");

    try {
      await onTestConnection(serverUrl);
    } catch (connectionError) {
      setError(connectionError.message);
    }
  };

  return (
    <KeyboardAvoidingView
      style={styles.loginWrapper}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <ScrollView
        contentContainerStyle={styles.loginScrollContent}
        keyboardShouldPersistTaps="handled"
      >
        <View style={styles.heroCard}>
          <Text style={styles.heroTitle}>Woodful Creations</Text>
          <Text style={styles.heroSubtitle}>
            Native Expo app for iPhone access to auth, dashboard, inventory,
            clients, payments, chat, and key operations.
          </Text>
        </View>

        <SectionCard
          title="Sign in"
          subtitle="Enter a reachable backend URL for your iPhone, then log in with an existing account."
        >
          <TextField
            label="API server URL"
            value={serverUrl}
            onChangeText={setServerUrl}
            placeholder="http://192.168.1.10:8000"
            autoCapitalize="none"
          />
          <View style={styles.connectionRow}>
            <PrimaryButton
              title={testingConnection ? "Checking..." : "Test connection"}
              onPress={handleConnectionTest}
              disabled={testingConnection}
              tone="secondary"
              fullWidth
            />
            {initialConnectionMessage ? (
              <Text style={styles.connectionMessage}>
                {initialConnectionMessage}
              </Text>
            ) : null}
          </View>
          <TextField
            label="Email"
            value={email}
            onChangeText={setEmail}
            placeholder="you@example.com"
            keyboardType="email-address"
            autoCapitalize="none"
          />
          <TextField
            label="Password"
            value={password}
            onChangeText={setPassword}
            placeholder="Enter your password"
            secureTextEntry
            autoCapitalize="none"
          />
          {error ? <Text style={styles.errorText}>{error}</Text> : null}
          <PrimaryButton
            title={loading ? "Signing in..." : "Sign in"}
            onPress={handleSubmit}
            disabled={loading}
            fullWidth
          />
        </SectionCard>

        <SectionCard
          title="What is included on mobile"
          subtitle="This native shell keeps the current backend contract and product concepts intact."
        >
          <View style={styles.featureList}>
            {[
              "Dashboard metrics and operational overview",
              "Inventory list plus add-item flow",
              "Client directory plus add-client flow",
              "Payments workspace for master users",
              "AI chat backed by the existing API",
              "Overview cards for estimates, attendance, interviews, and analytics",
            ].map((item) => (
              <Text key={item} style={styles.featureListItem}>
                {`\u2022 ${item}`}
              </Text>
            ))}
          </View>
        </SectionCard>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

function DashboardScreen({ api, user, apiBaseUrl, onNavigate }) {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [dashboard, setDashboard] = useState(null);
  const [error, setError] = useState("");

  const loadData = useCallback(async () => {
    setError("");

    try {
      const dashboardData = await api.getDashboard();
      setDashboard(dashboardData);
    } catch (loadError) {
      setError(loadError.message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [api]);

  useEffect(() => {
    setLoading(true);
    loadData();
  }, [loadData]);

  if (loading) {
    return <LoadingScreen label="Loading dashboard..." />;
  }

  const stats = dashboard?.stats || {};
  const userRole = dashboard?.userRole || user?.role || "user";

  return (
    <ScrollView
      contentContainerStyle={styles.screenContent}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={() => {
            setRefreshing(true);
            loadData();
          }}
        />
      }
    >
      <SectionCard
        title={`Welcome, ${getDisplayName(user)}`}
        subtitle={`Connected to ${apiBaseUrl}`}
      >
        <Text style={styles.mutedText}>
          This iPhone app uses the existing FastAPI backend and keeps the same
          core product areas available through mobile-friendly screens.
        </Text>
      </SectionCard>

      {error ? <Text style={styles.errorText}>{error}</Text> : null}

      <View style={styles.statGrid}>
        <StatCard label="Materials" value={stats.totalMaterials || 0} />
        <StatCard
          label="Low stock"
          value={stats.lowStockItems || 0}
          tone="warning"
        />
        <StatCard
          label="Inventory value"
          value={formatCurrency(stats.totalInventoryValue)}
        />
        <StatCard label="Active clients" value={stats.activeClients || 0} />
        <StatCard
          label="Pending estimates"
          value={stats.pendingEstimates || 0}
        />
        <StatCard
          label="Pending payments"
          value={formatCurrency(stats.pendingPayments)}
        />
        <StatCard label="AI chat" value="Ready" />
        <StatCard label="Role" value={userRole} />
      </View>

      <SectionCard title="Quick actions">
        <View style={styles.quickActionRow}>
          <PrimaryButton
            title="Open inventory"
            onPress={() => onNavigate("inventory")}
            fullWidth
          />
          <PrimaryButton
            title="Open clients"
            onPress={() => onNavigate("clients")}
            fullWidth
          />
        </View>
        <View style={styles.quickActionRow}>
          <PrimaryButton
            title="Open payments"
            onPress={() => onNavigate("payments")}
            fullWidth
          />
          <PrimaryButton
            title="Open chat"
            onPress={() => onNavigate("chat")}
            fullWidth
          />
        </View>
      </SectionCard>

      <SectionCard title="Additional modules">
        <Text style={styles.mutedText}>
          Estimates, attendance, interviews, and analytics remain part of the
          product model and are represented in the native app through the
          operations overview screen.
        </Text>
      </SectionCard>
    </ScrollView>
  );
}

function InventoryScreen({ api }) {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [products, setProducts] = useState([]);
  const [materials, setMaterials] = useState({});
  const [searchTerm, setSearchTerm] = useState("");
  const [error, setError] = useState("");
  const [modalVisible, setModalVisible] = useState(false);
  const [form, setForm] = useState(INVENTORY_FORM_DEFAULTS);
  const [saving, setSaving] = useState(false);

  const loadData = useCallback(async () => {
    setError("");

    try {
      const [inventoryData, materialData] = await Promise.all([
        api.getInventory(),
        api.getMaterialOptions(),
      ]);

      setProducts(inventoryData);
      setMaterials(materialData.materials || {});

      const firstMaterial = Object.keys(materialData.materials || {})[0] || "";
      setForm((currentForm) => ({
        ...currentForm,
        material_type: currentForm.material_type || firstMaterial,
        thickness:
          currentForm.thickness ||
          String((materialData.materials?.[firstMaterial] || [])[0] || ""),
      }));
    } catch (loadError) {
      setError(loadError.message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [api]);

  useEffect(() => {
    setLoading(true);
    loadData();
  }, [loadData]);

  const filteredProducts = products.filter((product) => {
    const haystack = [
      product.material_type,
      product.category,
      product.supplier,
      product.sku,
      product.description,
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();

    return haystack.includes(searchTerm.trim().toLowerCase());
  });

  const thicknessOptions = materials[form.material_type] || [];

  const handleMaterialChange = (material) => {
    setForm((currentForm) => ({
      ...currentForm,
      material_type: material,
      thickness: String((materials[material] || [])[0] || ""),
    }));
  };

  const handleCreate = async () => {
    setSaving(true);
    setError("");

    try {
      await api.addInventoryItem({
        ...form,
        thickness: Number(form.thickness),
        quantity: Number(form.quantity),
        min_quantity: Number(form.min_quantity),
        price_per_unit: Number(form.price_per_unit),
      });

      setModalVisible(false);
      setForm((currentForm) => ({
        ...INVENTORY_FORM_DEFAULTS,
        material_type: currentForm.material_type,
        thickness: currentForm.thickness,
      }));
      setRefreshing(true);
      await loadData();
    } catch (saveError) {
      setError(saveError.message);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <LoadingScreen label="Loading inventory..." />;
  }

  return (
    <ScrollView
      contentContainerStyle={styles.screenContent}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={() => {
            setRefreshing(true);
            loadData();
          }}
        />
      }
    >
      <SectionCard
        title="Inventory"
        subtitle="Review stock levels and add new material entries from iPhone."
        action={
          <PrimaryButton
            title="Add item"
            onPress={() => setModalVisible(true)}
          />
        }
      >
        <TextField
          label="Search"
          value={searchTerm}
          onChangeText={setSearchTerm}
          placeholder="Material, category, supplier, or SKU"
          autoCapitalize="none"
        />
        <Text style={styles.mutedText}>
          {filteredProducts.length} items shown,{" "}
          {products.filter((item) => item.quantity <= item.min_quantity).length}{" "}
          low-stock items.
        </Text>
      </SectionCard>

      {error ? <Text style={styles.errorText}>{error}</Text> : null}

      {filteredProducts.length === 0 ? (
        <EmptyState
          title="No inventory items found"
          description="Add a material or change your search to see matching stock."
        />
      ) : (
        filteredProducts.map((product) => {
          const isLowStock = product.quantity <= product.min_quantity;

          return (
            <SectionCard
              key={product.id}
              title={`${product.material_type} - ${product.thickness} mm`}
              subtitle={`${product.category || "Uncategorized"}${product.supplier ? ` • ${product.supplier}` : ""}`}
            >
              <View style={styles.detailRow}>
                <Text style={styles.detailLabel}>Quantity</Text>
                <Text style={styles.detailValue}>
                  {product.quantity} {product.unit}
                </Text>
              </View>
              <View style={styles.detailRow}>
                <Text style={styles.detailLabel}>Minimum</Text>
                <Text style={styles.detailValue}>{product.min_quantity}</Text>
              </View>
              <View style={styles.detailRow}>
                <Text style={styles.detailLabel}>Price</Text>
                <Text style={styles.detailValue}>
                  {formatCurrency(product.price_per_unit)}
                </Text>
              </View>
              {product.sku ? (
                <View style={styles.detailRow}>
                  <Text style={styles.detailLabel}>SKU</Text>
                  <Text style={styles.detailValue}>{product.sku}</Text>
                </View>
              ) : null}
              {product.description ? (
                <Text style={styles.itemDescription}>
                  {product.description}
                </Text>
              ) : null}
              <Text
                style={[styles.statusBadge, isLowStock && styles.warningBadge]}
              >
                {isLowStock ? "Low stock" : "In stock"}
              </Text>
            </SectionCard>
          );
        })
      )}

      <Modal visible={modalVisible} animationType="slide">
        <SafeAreaView style={styles.modalScreen}>
          <ScrollView contentContainerStyle={styles.modalContent}>
            <SectionCard
              title="Add inventory item"
              subtitle="Create a new material record using the existing inventory API."
              action={
                <PrimaryButton
                  title="Close"
                  onPress={() => setModalVisible(false)}
                  tone="secondary"
                />
              }
            >
              <Text style={styles.fieldLabel}>Material type</Text>
              <View style={styles.chipWrap}>
                {Object.keys(materials).map((material) => (
                  <Chip
                    key={material}
                    label={material}
                    selected={form.material_type === material}
                    onPress={() => handleMaterialChange(material)}
                  />
                ))}
              </View>

              <Text style={styles.fieldLabel}>Thickness</Text>
              <View style={styles.chipWrap}>
                {thicknessOptions.map((thickness) => (
                  <Chip
                    key={thickness}
                    label={`${thickness} mm`}
                    selected={String(thickness) === String(form.thickness)}
                    onPress={() =>
                      setForm((currentForm) => ({
                        ...currentForm,
                        thickness: String(thickness),
                      }))
                    }
                  />
                ))}
              </View>

              <TextField
                label="Category"
                value={form.category}
                onChangeText={(value) =>
                  setForm((currentForm) => ({
                    ...currentForm,
                    category: value,
                  }))
                }
                placeholder="plywood, laminate, hardware"
              />
              <TextField
                label="Description"
                value={form.description}
                onChangeText={(value) =>
                  setForm((currentForm) => ({
                    ...currentForm,
                    description: value,
                  }))
                }
                placeholder="Optional notes"
                multiline
              />
              <TextField
                label="Quantity"
                value={String(form.quantity)}
                onChangeText={(value) =>
                  setForm((currentForm) => ({
                    ...currentForm,
                    quantity: value,
                  }))
                }
                keyboardType="numeric"
                placeholder="0"
              />
              <TextField
                label="Minimum quantity"
                value={String(form.min_quantity)}
                onChangeText={(value) =>
                  setForm((currentForm) => ({
                    ...currentForm,
                    min_quantity: value,
                  }))
                }
                keyboardType="numeric"
                placeholder="10"
              />
              <TextField
                label="Price per unit"
                value={String(form.price_per_unit)}
                onChangeText={(value) =>
                  setForm((currentForm) => ({
                    ...currentForm,
                    price_per_unit: value,
                  }))
                }
                keyboardType="numeric"
                placeholder="0.00"
              />
              <TextField
                label="Unit"
                value={form.unit}
                onChangeText={(value) =>
                  setForm((currentForm) => ({ ...currentForm, unit: value }))
                }
                placeholder="sheets"
              />
              <TextField
                label="SKU"
                value={form.sku}
                onChangeText={(value) =>
                  setForm((currentForm) => ({ ...currentForm, sku: value }))
                }
                placeholder="Optional SKU"
                autoCapitalize="characters"
              />
              <TextField
                label="Supplier"
                value={form.supplier}
                onChangeText={(value) =>
                  setForm((currentForm) => ({
                    ...currentForm,
                    supplier: value,
                  }))
                }
                placeholder="Optional supplier"
              />

              {error ? <Text style={styles.errorText}>{error}</Text> : null}
              <PrimaryButton
                title={saving ? "Saving..." : "Save item"}
                onPress={handleCreate}
                disabled={saving}
                fullWidth
              />
            </SectionCard>
          </ScrollView>
        </SafeAreaView>
      </Modal>
    </ScrollView>
  );
}

function ClientsScreen({ api }) {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [clients, setClients] = useState([]);
  const [error, setError] = useState("");
  const [modalVisible, setModalVisible] = useState(false);
  const [form, setForm] = useState(CLIENT_FORM_DEFAULTS);
  const [saving, setSaving] = useState(false);

  const loadData = useCallback(async () => {
    setError("");

    try {
      const clientData = await api.getClients();
      setClients(clientData);
    } catch (loadError) {
      setError(loadError.message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [api]);

  useEffect(() => {
    setLoading(true);
    loadData();
  }, [loadData]);

  const handleCreate = async () => {
    setSaving(true);
    setError("");

    try {
      await api.addClient(form);
      setForm(CLIENT_FORM_DEFAULTS);
      setModalVisible(false);
      setRefreshing(true);
      await loadData();
    } catch (saveError) {
      setError(saveError.message);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <LoadingScreen label="Loading clients..." />;
  }

  return (
    <ScrollView
      contentContainerStyle={styles.screenContent}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={() => {
            setRefreshing(true);
            loadData();
          }}
        />
      }
    >
      <SectionCard
        title="Clients"
        subtitle="Browse client records and capture new client details from iPhone."
        action={
          <PrimaryButton
            title="Add client"
            onPress={() => setModalVisible(true)}
          />
        }
      >
        <Text style={styles.mutedText}>
          {clients.length} active client records.
        </Text>
      </SectionCard>

      {error ? <Text style={styles.errorText}>{error}</Text> : null}

      {clients.length === 0 ? (
        <EmptyState
          title="No clients found"
          description="Create a client record to keep project and payment context together."
        />
      ) : (
        clients.map((client) => (
          <SectionCard
            key={client.id}
            title={client.name}
            subtitle={client.company || "Independent client"}
          >
            <View style={styles.detailRow}>
              <Text style={styles.detailLabel}>Email</Text>
              <Text style={styles.detailValue}>{client.email}</Text>
            </View>
            <View style={styles.detailRow}>
              <Text style={styles.detailLabel}>Phone</Text>
              <Text style={styles.detailValue}>{client.phone}</Text>
            </View>
            {client.address ? (
              <Text style={styles.itemDescription}>{client.address}</Text>
            ) : null}
          </SectionCard>
        ))
      )}

      <Modal visible={modalVisible} animationType="slide">
        <SafeAreaView style={styles.modalScreen}>
          <ScrollView contentContainerStyle={styles.modalContent}>
            <SectionCard
              title="Add client"
              subtitle="Create a client record with the current backend schema."
              action={
                <PrimaryButton
                  title="Close"
                  onPress={() => setModalVisible(false)}
                  tone="secondary"
                />
              }
            >
              <TextField
                label="Name"
                value={form.name}
                onChangeText={(value) =>
                  setForm((currentForm) => ({ ...currentForm, name: value }))
                }
                placeholder="Client name"
              />
              <TextField
                label="Email"
                value={form.email}
                onChangeText={(value) =>
                  setForm((currentForm) => ({ ...currentForm, email: value }))
                }
                placeholder="client@example.com"
                keyboardType="email-address"
                autoCapitalize="none"
              />
              <TextField
                label="Phone"
                value={form.phone}
                onChangeText={(value) =>
                  setForm((currentForm) => ({ ...currentForm, phone: value }))
                }
                placeholder="Phone number"
                keyboardType="phone-pad"
              />
              <TextField
                label="Company"
                value={form.company}
                onChangeText={(value) =>
                  setForm((currentForm) => ({ ...currentForm, company: value }))
                }
                placeholder="Optional company"
              />
              <TextField
                label="Address"
                value={form.address}
                onChangeText={(value) =>
                  setForm((currentForm) => ({ ...currentForm, address: value }))
                }
                placeholder="Optional address"
                multiline
              />
              {error ? <Text style={styles.errorText}>{error}</Text> : null}
              <PrimaryButton
                title={saving ? "Saving..." : "Save client"}
                onPress={handleCreate}
                disabled={saving}
                fullWidth
              />
            </SectionCard>
          </ScrollView>
        </SafeAreaView>
      </Modal>
    </ScrollView>
  );
}

function PaymentsScreen({ api, user }) {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [payments, setPayments] = useState([]);
  const [error, setError] = useState("");
  const [modalVisible, setModalVisible] = useState(false);
  const [form, setForm] = useState(PAYMENT_FORM_DEFAULTS);
  const [saving, setSaving] = useState(false);

  const isMasterUser = user?.role === "master";

  const loadData = useCallback(async () => {
    setError("");

    try {
      const paymentData = await api.getPayments();
      setPayments(paymentData);
    } catch (loadError) {
      setError(loadError.message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [api]);

  useEffect(() => {
    setLoading(true);
    loadData();
  }, [loadData]);

  const handleCreate = async () => {
    setSaving(true);
    setError("");

    try {
      await api.addPayment({
        ...form,
        related_id: Number(form.related_id),
        amount: Number(form.amount),
        payment_date: new Date().toISOString(),
      });
      setForm(PAYMENT_FORM_DEFAULTS);
      setModalVisible(false);
      setRefreshing(true);
      await loadData();
    } catch (saveError) {
      setError(saveError.message);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <LoadingScreen label="Loading payments..." />;
  }

  return (
    <ScrollView
      contentContainerStyle={styles.screenContent}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={() => {
            setRefreshing(true);
            loadData();
          }}
        />
      }
    >
      <SectionCard
        title="Payments"
        subtitle="Track supplier or project-related payments with the native client."
        action={
          isMasterUser ? (
            <PrimaryButton
              title="Add payment"
              onPress={() => setModalVisible(true)}
            />
          ) : null
        }
      >
        <Text style={styles.mutedText}>
          {payments.length} payment records found. Payment creation is limited
          to master users in the mobile UI.
        </Text>
      </SectionCard>

      {!isMasterUser ? (
        <SectionCard title="Access note">
          <Text style={styles.mutedText}>
            Payments are sensitive. Sign in with a master user to create new
            entries from the iPhone app.
          </Text>
        </SectionCard>
      ) : null}

      {error ? <Text style={styles.errorText}>{error}</Text> : null}

      {payments.length === 0 ? (
        <EmptyState
          title="No payments found"
          description="Add a payment record to track outgoing or incoming activity."
        />
      ) : (
        payments.map((payment) => (
          <SectionCard
            key={payment.id}
            title={`${payment.payment_type} • ${formatCurrency(payment.amount)}`}
            subtitle={`${payment.payment_method} • ${payment.status}`}
          >
            <View style={styles.detailRow}>
              <Text style={styles.detailLabel}>Related ID</Text>
              <Text style={styles.detailValue}>{payment.related_id}</Text>
            </View>
            <View style={styles.detailRow}>
              <Text style={styles.detailLabel}>Date</Text>
              <Text style={styles.detailValue}>
                {formatDate(payment.payment_date)}
              </Text>
            </View>
            {payment.description ? (
              <Text style={styles.itemDescription}>{payment.description}</Text>
            ) : null}
          </SectionCard>
        ))
      )}

      <Modal visible={modalVisible} animationType="slide">
        <SafeAreaView style={styles.modalScreen}>
          <ScrollView contentContainerStyle={styles.modalContent}>
            <SectionCard
              title="Add payment"
              subtitle="Create a payment entry with the current payment API contract."
              action={
                <PrimaryButton
                  title="Close"
                  onPress={() => setModalVisible(false)}
                  tone="secondary"
                />
              }
            >
              <TextField
                label="Payment type"
                value={form.payment_type}
                onChangeText={(value) =>
                  setForm((currentForm) => ({
                    ...currentForm,
                    payment_type: value,
                  }))
                }
                placeholder="supplier, project, invoice"
              />
              <TextField
                label="Related ID"
                value={String(form.related_id)}
                onChangeText={(value) =>
                  setForm((currentForm) => ({
                    ...currentForm,
                    related_id: value,
                  }))
                }
                keyboardType="numeric"
                placeholder="Numeric record ID"
              />
              <TextField
                label="Amount"
                value={String(form.amount)}
                onChangeText={(value) =>
                  setForm((currentForm) => ({ ...currentForm, amount: value }))
                }
                keyboardType="numeric"
                placeholder="0.00"
              />
              <TextField
                label="Payment method"
                value={form.payment_method}
                onChangeText={(value) =>
                  setForm((currentForm) => ({
                    ...currentForm,
                    payment_method: value,
                  }))
                }
                placeholder="bank_transfer, cash, upi"
              />
              <TextField
                label="Description"
                value={form.description}
                onChangeText={(value) =>
                  setForm((currentForm) => ({
                    ...currentForm,
                    description: value,
                  }))
                }
                placeholder="Optional note"
                multiline
              />
              {error ? <Text style={styles.errorText}>{error}</Text> : null}
              <PrimaryButton
                title={saving ? "Saving..." : "Save payment"}
                onPress={handleCreate}
                disabled={saving}
                fullWidth
              />
            </SectionCard>
          </ScrollView>
        </SafeAreaView>
      </Modal>
    </ScrollView>
  );
}

function ChatScreen({ api, conversationId, onConversationIdChange }) {
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [suggestions, setSuggestions] = useState([]);

  const sendMessage = async (message) => {
    const nextMessage = message.trim();

    if (!nextMessage || loading) {
      return;
    }

    setLoading(true);
    setError("");
    setMessages((currentMessages) => [
      ...currentMessages,
      { id: `${Date.now()}-user`, role: "user", text: nextMessage },
    ]);
    setInputValue("");

    try {
      const response = await api.sendChatMessage(nextMessage, conversationId);

      if (response.conversation_id) {
        onConversationIdChange(response.conversation_id);
      }

      setMessages((currentMessages) => [
        ...currentMessages,
        {
          id: `${Date.now()}-assistant`,
          role: "assistant",
          text: response.response,
        },
      ]);
      setSuggestions(response.suggestions || []);
    } catch (sendError) {
      setError(sendError.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <ScrollView contentContainerStyle={styles.screenContent}>
      <SectionCard
        title="AI Chat"
        subtitle="Use the existing backend chat endpoint for mobile business assistance."
      >
        <Text style={styles.mutedText}>
          Ask about stock, clients, orders, or day-to-day operations.
        </Text>
      </SectionCard>

      {messages.length === 0 ? (
        <EmptyState
          title="Start a conversation"
          description="Send a message to begin a backend-powered chat session."
        />
      ) : (
        messages.map((message) => (
          <View
            key={message.id}
            style={[
              styles.chatBubble,
              message.role === "user"
                ? styles.userBubble
                : styles.assistantBubble,
            ]}
          >
            <Text
              style={[
                styles.chatRole,
                message.role === "user" && styles.userBubbleText,
              ]}
            >
              {message.role === "user" ? "You" : "Assistant"}
            </Text>
            <Text
              style={[
                styles.chatText,
                message.role === "user" && styles.userBubbleText,
              ]}
            >
              {message.text}
            </Text>
          </View>
        ))
      )}

      {suggestions.length > 0 ? (
        <SectionCard title="Suggestions">
          <View style={styles.chipWrap}>
            {suggestions.map((suggestion) => (
              <Chip
                key={suggestion}
                label={suggestion}
                selected={false}
                onPress={() => sendMessage(suggestion)}
              />
            ))}
          </View>
        </SectionCard>
      ) : null}

      <SectionCard title="Send message">
        <TextField
          label="Message"
          value={inputValue}
          onChangeText={setInputValue}
          placeholder="Ask about inventory, clients, or operations"
          multiline
        />
        {error ? <Text style={styles.errorText}>{error}</Text> : null}
        <PrimaryButton
          title={loading ? "Sending..." : "Send"}
          onPress={() => sendMessage(inputValue)}
          disabled={loading}
          fullWidth
        />
      </SectionCard>
    </ScrollView>
  );
}

function ModulesScreen({ api }) {
  const [loading, setLoading] = useState(true);
  const [pendingPayments, setPendingPayments] = useState(0);
  const [error, setError] = useState("");

  const loadData = useCallback(async () => {
    setError("");

    try {
      const dashboard = await api.getDashboard();
      setPendingPayments(dashboard?.stats?.pendingPayments || 0);
    } catch (loadError) {
      setError(loadError.message);
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    setLoading(true);
    loadData();
  }, [loadData]);

  if (loading) {
    return <LoadingScreen label="Loading modules..." />;
  }

  return (
    <ScrollView contentContainerStyle={styles.screenContent}>
      <SectionCard
        title="Additional product modules"
        subtitle="Live backend overviews keep the broader product surface visible on iPhone."
      >
        <Text style={styles.mutedText}>
          The mobile client focuses on the most-used daily workflows while still
          surfacing the rest of the product model.
        </Text>
      </SectionCard>

      {error ? <Text style={styles.errorText}>{error}</Text> : null}

      <SectionCard title="Estimates" subtitle="Native overview ready">
        <Text style={styles.mutedText}>
          Estimate tracking remains part of the product model and can be
          expanded into deeper native create and edit flows without changing the
          backend contract used by the web application.
        </Text>
      </SectionCard>

      <SectionCard title="Attendance" subtitle="Native overview ready">
        <Text style={styles.mutedText}>
          Attendance remains an app concept on mobile, with the current iPhone
          build focused first on the most-used operational workflows.
        </Text>
      </SectionCard>

      <SectionCard title="Interviews" subtitle="Native overview ready">
        <Text style={styles.mutedText}>
          Recruitment workflows can be layered onto the same authenticated
          mobile shell when the team is ready to extend beyond the initial
          iPhone MVP.
        </Text>
      </SectionCard>

      <SectionCard
        title="Analytics"
        subtitle={`${formatCurrency(pendingPayments)} pending payments`}
      >
        <Text style={styles.mutedText}>
          Dashboard totals and module counts provide a mobile-friendly analytics
          overview for quick decision making.
        </Text>
      </SectionCard>
    </ScrollView>
  );
}

function LoadingScreen({ label }) {
  return (
    <View style={styles.loadingScreen}>
      <ActivityIndicator size="large" color="#6d4c41" />
      <Text style={styles.loadingText}>{label}</Text>
    </View>
  );
}

function renderActiveScreen({
  activeTab,
  api,
  apiBaseUrl,
  conversationId,
  onConversationIdChange,
  onNavigate,
  user,
}) {
  switch (activeTab) {
    case "inventory":
      return <InventoryScreen api={api} />;
    case "clients":
      return <ClientsScreen api={api} />;
    case "payments":
      return <PaymentsScreen api={api} user={user} />;
    case "chat":
      return (
        <ChatScreen
          api={api}
          conversationId={conversationId}
          onConversationIdChange={onConversationIdChange}
        />
      );
    case "modules":
      return <ModulesScreen api={api} />;
    case "dashboard":
    default:
      return (
        <DashboardScreen
          api={api}
          apiBaseUrl={apiBaseUrl}
          onNavigate={onNavigate}
          user={user}
        />
      );
  }
}

export default function WoodfulMobileApp() {
  const [booting, setBooting] = useState(true);
  const [testingConnection, setTestingConnection] = useState(false);
  const [connectionMessage, setConnectionMessage] = useState("");
  const [apiBaseUrl, setApiBaseUrl] = useState(getDefaultApiBaseUrl());
  const [activeTab, setActiveTab] = useState("dashboard");
  const [conversationId, setConversationId] = useState(null);
  const [token, setToken] = useState(null);
  const [user, setUser] = useState(null);

  const clearSession = useCallback(async () => {
    await AsyncStorage.multiRemove([
      STORAGE_KEYS.token,
      STORAGE_KEYS.user,
      STORAGE_KEYS.conversationId,
    ]);
    setToken(null);
    setUser(null);
    setConversationId(null);
    setActiveTab("dashboard");
  }, []);

  useEffect(() => {
    const hydrate = async () => {
      try {
        const storedValues = await AsyncStorage.multiGet([
          STORAGE_KEYS.apiUrl,
          STORAGE_KEYS.conversationId,
          STORAGE_KEYS.token,
          STORAGE_KEYS.user,
        ]);

        const valueMap = Object.fromEntries(storedValues);

        if (valueMap[STORAGE_KEYS.apiUrl]) {
          setApiBaseUrl(normalizeApiBaseUrl(valueMap[STORAGE_KEYS.apiUrl]));
        }

        if (valueMap[STORAGE_KEYS.conversationId]) {
          setConversationId(valueMap[STORAGE_KEYS.conversationId]);
        }

        if (valueMap[STORAGE_KEYS.token] && valueMap[STORAGE_KEYS.user]) {
          setToken(valueMap[STORAGE_KEYS.token]);
          setUser(JSON.parse(valueMap[STORAGE_KEYS.user]));
        }
      } catch (error) {
        Alert.alert(
          "Session reset",
          "Stored mobile session data could not be restored.",
        );
      } finally {
        setBooting(false);
      }
    };

    hydrate();
  }, []);

  const api = useMemo(
    () =>
      createMobileApi({
        baseURL: apiBaseUrl,
        getToken: () => token,
        onUnauthorized: async () => {
          await clearSession();
          Alert.alert("Session expired", "Please sign in again.");
        },
      }),
    [apiBaseUrl, clearSession, token],
  );

  const handleConversationIdChange = useCallback(async (nextConversationId) => {
    setConversationId(nextConversationId);

    if (nextConversationId) {
      await AsyncStorage.setItem(
        STORAGE_KEYS.conversationId,
        nextConversationId,
      );
    } else {
      await AsyncStorage.removeItem(STORAGE_KEYS.conversationId);
    }
  }, []);

  const handleLogin = useCallback(async ({ email, password, serverUrl }) => {
    const normalizedApiBaseUrl = normalizeApiBaseUrl(serverUrl);
    const authApi = createMobileApi({ baseURL: normalizedApiBaseUrl });
    const session = await authApi.login(email, password);

    await AsyncStorage.multiSet([
      [STORAGE_KEYS.apiUrl, normalizedApiBaseUrl],
      [STORAGE_KEYS.token, session.token],
      [STORAGE_KEYS.user, JSON.stringify(session.user)],
    ]);

    setApiBaseUrl(normalizedApiBaseUrl);
    setToken(session.token);
    setUser(session.user);
    setConnectionMessage(`Connected to ${normalizedApiBaseUrl}`);
  }, []);

  const handleTestConnection = useCallback(async (serverUrl) => {
    setTestingConnection(true);

    try {
      const normalizedApiBaseUrl = normalizeApiBaseUrl(serverUrl);
      const authApi = createMobileApi({ baseURL: normalizedApiBaseUrl });
      const health = await authApi.health();
      const message = `${health.service} ${health.version} is reachable`;

      setConnectionMessage(message);
      await AsyncStorage.setItem(STORAGE_KEYS.apiUrl, normalizedApiBaseUrl);
      setApiBaseUrl(normalizedApiBaseUrl);
    } finally {
      setTestingConnection(false);
    }
  }, []);

  if (booting) {
    return (
      <SafeAreaView style={styles.safeArea}>
        <StatusBar style="dark" />
        <LoadingScreen label="Preparing mobile workspace..." />
      </SafeAreaView>
    );
  }

  if (!token || !user) {
    return (
      <SafeAreaView style={styles.safeArea}>
        <StatusBar style="dark" />
        <LoginScreen
          apiBaseUrl={apiBaseUrl}
          initialConnectionMessage={connectionMessage}
          onLogin={handleLogin}
          onTestConnection={handleTestConnection}
          testingConnection={testingConnection}
        />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar style="dark" />
      <View style={styles.appShell}>
        <View style={styles.topBar}>
          <View style={styles.topBarText}>
            <Text style={styles.topBarTitle}>Woodful Creations</Text>
            <Text style={styles.topBarSubtitle}>{getDisplayName(user)}</Text>
          </View>
          <PrimaryButton
            title="Log out"
            onPress={clearSession}
            tone="secondary"
          />
        </View>

        <View style={styles.contentArea}>
          {renderActiveScreen({
            activeTab,
            api,
            apiBaseUrl,
            conversationId,
            onConversationIdChange: handleConversationIdChange,
            onNavigate: setActiveTab,
            user,
          })}
        </View>

        <View style={styles.tabBar}>
          {TAB_ITEMS.map((item) => {
            const selected = activeTab === item.key;

            return (
              <Pressable
                key={item.key}
                style={[styles.tabButton, selected && styles.tabButtonActive]}
                onPress={() => setActiveTab(item.key)}
              >
                <Text
                  style={[
                    styles.tabButtonText,
                    selected && styles.tabButtonTextActive,
                  ]}
                >
                  {item.label}
                </Text>
              </Pressable>
            );
          })}
        </View>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: "#f4efe9",
  },
  appShell: {
    flex: 1,
  },
  topBar: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: "#fff",
    borderBottomWidth: 1,
    borderBottomColor: "#e0d7cf",
  },
  topBarText: {
    flex: 1,
    marginRight: 12,
  },
  topBarTitle: {
    fontSize: 20,
    fontWeight: "700",
    color: "#3e2723",
  },
  topBarSubtitle: {
    marginTop: 4,
    fontSize: 13,
    color: "#6d4c41",
  },
  contentArea: {
    flex: 1,
  },
  loginWrapper: {
    flex: 1,
  },
  loginScrollContent: {
    padding: 16,
    paddingBottom: 32,
  },
  heroCard: {
    backgroundColor: "#6d4c41",
    borderRadius: 20,
    padding: 20,
    marginBottom: 16,
  },
  heroTitle: {
    color: "#fff",
    fontSize: 28,
    fontWeight: "700",
  },
  heroSubtitle: {
    color: "#f3e9e2",
    fontSize: 15,
    lineHeight: 22,
    marginTop: 8,
  },
  screenContent: {
    padding: 16,
    paddingBottom: 120,
  },
  sectionCard: {
    backgroundColor: "#fff",
    borderRadius: 18,
    padding: 16,
    marginBottom: 16,
    shadowColor: "#000",
    shadowOpacity: 0.05,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 3 },
    elevation: 2,
  },
  sectionHeader: {
    flexDirection: "row",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: 12,
    marginBottom: 12,
  },
  sectionHeaderText: {
    flex: 1,
  },
  sectionTitle: {
    fontSize: 20,
    fontWeight: "700",
    color: "#3e2723",
  },
  sectionSubtitle: {
    marginTop: 6,
    fontSize: 14,
    lineHeight: 20,
    color: "#7a6c63",
  },
  statGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "space-between",
    marginBottom: 8,
  },
  statCard: {
    width: "48%",
    backgroundColor: "#fff",
    borderRadius: 18,
    padding: 16,
    marginBottom: 12,
  },
  statCardWarning: {
    borderWidth: 1,
    borderColor: "#d97706",
  },
  statLabel: {
    color: "#7a6c63",
    fontSize: 13,
    marginBottom: 8,
  },
  statValue: {
    color: "#3e2723",
    fontSize: 20,
    fontWeight: "700",
  },
  mutedText: {
    color: "#7a6c63",
    fontSize: 14,
    lineHeight: 21,
  },
  quickActionRow: {
    flexDirection: "row",
    gap: 12,
    marginBottom: 12,
  },
  button: {
    backgroundColor: "#6d4c41",
    paddingHorizontal: 14,
    paddingVertical: 12,
    borderRadius: 12,
    alignItems: "center",
    justifyContent: "center",
  },
  secondaryButton: {
    backgroundColor: "#efe4dc",
  },
  fullWidthButton: {
    flex: 1,
  },
  disabledButton: {
    opacity: 0.6,
  },
  buttonText: {
    color: "#fff",
    fontWeight: "600",
  },
  secondaryButtonText: {
    color: "#6d4c41",
  },
  featureList: {
    gap: 8,
  },
  featureListItem: {
    color: "#4e342e",
    fontSize: 14,
    lineHeight: 21,
  },
  connectionRow: {
    gap: 10,
    marginBottom: 12,
  },
  connectionMessage: {
    color: "#2e7d32",
    fontSize: 13,
  },
  fieldGroup: {
    marginBottom: 12,
  },
  fieldLabel: {
    color: "#5d4037",
    fontSize: 13,
    fontWeight: "600",
    marginBottom: 6,
  },
  input: {
    minHeight: 48,
    borderWidth: 1,
    borderColor: "#d7ccc8",
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 15,
    color: "#3e2723",
    backgroundColor: "#fcfaf8",
  },
  multilineInput: {
    minHeight: 96,
    textAlignVertical: "top",
  },
  errorText: {
    color: "#b91c1c",
    marginBottom: 12,
    fontSize: 13,
  },
  emptyState: {
    backgroundColor: "#fff",
    borderRadius: 18,
    padding: 20,
    alignItems: "center",
  },
  emptyStateTitle: {
    color: "#3e2723",
    fontSize: 18,
    fontWeight: "700",
    marginBottom: 8,
  },
  emptyStateText: {
    color: "#7a6c63",
    fontSize: 14,
    lineHeight: 21,
    textAlign: "center",
  },
  detailRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginBottom: 8,
    gap: 16,
  },
  detailLabel: {
    color: "#7a6c63",
    fontSize: 13,
  },
  detailValue: {
    color: "#3e2723",
    fontSize: 14,
    fontWeight: "600",
    flexShrink: 1,
    textAlign: "right",
  },
  itemDescription: {
    color: "#5d4037",
    fontSize: 14,
    lineHeight: 20,
    marginTop: 6,
  },
  statusBadge: {
    marginTop: 12,
    alignSelf: "flex-start",
    backgroundColor: "#e8f5e9",
    color: "#2e7d32",
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 999,
    fontSize: 12,
    fontWeight: "600",
    overflow: "hidden",
  },
  warningBadge: {
    backgroundColor: "#fff3cd",
    color: "#b45309",
  },
  modalScreen: {
    flex: 1,
    backgroundColor: "#f4efe9",
  },
  modalContent: {
    padding: 16,
    paddingBottom: 32,
  },
  chipWrap: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 10,
    marginBottom: 12,
  },
  chip: {
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 8,
    backgroundColor: "#efe4dc",
  },
  chipSelected: {
    backgroundColor: "#6d4c41",
  },
  chipText: {
    color: "#5d4037",
    fontSize: 13,
    fontWeight: "600",
  },
  chipTextSelected: {
    color: "#fff",
  },
  chatBubble: {
    borderRadius: 18,
    padding: 14,
    marginBottom: 12,
    maxWidth: "100%",
  },
  assistantBubble: {
    backgroundColor: "#fff",
  },
  userBubble: {
    backgroundColor: "#6d4c41",
  },
  chatRole: {
    fontSize: 12,
    fontWeight: "700",
    marginBottom: 6,
    color: "#6d4c41",
  },
  chatText: {
    color: "#3e2723",
    fontSize: 14,
    lineHeight: 20,
  },
  userBubbleText: {
    color: "#fff",
  },
  tabBar: {
    flexDirection: "row",
    flexWrap: "wrap",
    backgroundColor: "#fff",
    borderTopWidth: 1,
    borderTopColor: "#e0d7cf",
    paddingHorizontal: 8,
    paddingTop: 8,
    paddingBottom: 12,
  },
  tabButton: {
    width: "33.33%",
    paddingVertical: 10,
    paddingHorizontal: 4,
    alignItems: "center",
    borderRadius: 10,
  },
  tabButtonActive: {
    backgroundColor: "#efe4dc",
  },
  tabButtonText: {
    fontSize: 12,
    color: "#7a6c63",
    fontWeight: "600",
  },
  tabButtonTextActive: {
    color: "#6d4c41",
  },
  loadingScreen: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    gap: 12,
  },
  loadingText: {
    color: "#6d4c41",
    fontSize: 15,
  },
});
