import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { dashboardAPI, dailyTasksAPI, purchasesAPI, paymentsAPI, productionJobsAPI, ordersAPI, clientActivitiesAPI } from '../../../utils/api';
import { KpiCard } from '../../../components/common/UI';
import { Card } from '../../../components/common/UI';
import { Table } from '../../../components/common/UI';
import { SimpleBarChart } from '../../../components/common/UI';
import { LoadingShell } from '../../../components/Infrastructure';
import { formatCurrency, today } from '../../../utils/utils';
import {
  AlertTriangleIcon, TruckIcon, PaymentIcon, EmployeeIcon, ArrowUpRightIcon,
  CompassIcon, CheckCircleIcon, PurchaseIcon,
} from '../../../components/icons';

/* ==========================================================================
   Atelier Command Centre — Home dashboard redesign.
   Restyled per the Stitch "Atelier Command Centre" mockups (dark + light
   theme) the user supplied: a compact KPI strip, a three-column
   "operations snapshot" (Orders Pipeline + Order Health + Attention
   accordion / Inventory Health + Today's Focus / Production Execution +
   Task Progress), then the existing hero metrics, follow-ups, business
   charts and recent activity sections below, all restyled to the new
   palette. Every number below is real data already fetched by
   DashboardPage - nothing here is mock/placeholder data the way the
   Stitch source HTML was. Layout is fluid/responsive (CSS grid that
   collapses to one column on narrow viewports) rather than the
   mockup's literal fixed 1440x930 floating window, per the app-wide +
   full-viewport scope agreed for this redesign.
   ========================================================================== */

// --- Small presentational pieces (kept in this file - only ever used
// on the Home dashboard, not shared elsewhere) ---

function KpiStrip({ items }) {
  return (
    <div className="kpi-strip">
      {items.map((item) => (
        <div className={`kpi-pill kpi-pill-${item.tone || 'default'}`} key={item.label}>
          <item.icon className="kpi-pill-icon" />
          <span className="kpi-pill-label">{item.label}</span>
          <span className="kpi-pill-value">{item.value}</span>
        </div>
      ))}
    </div>
  );
}

// Generic small vertical bar visualization shared by the Orders
// Pipeline and Inventory Health cards - real data in, no chart
// library, matches the Atelier design's bar-with-caption look.
function VerticalBars({ bars }) {
  const max = Math.max(1, ...bars.map((b) => b.value));
  return (
    <div className="vbar-chart">
      {bars.map((b) => (
        <div className="vbar-col" key={b.label} title={`${b.label}: ${b.value}`}>
          <span className="vbar-value">{b.value}</span>
          <div className="vbar-track">
            <div
              className="vbar-fill"
              style={{ height: `${Math.max(6, (b.value / max) * 100)}%`, background: b.color || 'var(--color-gold)' }}
            />
          </div>
          <span className="vbar-label">{b.label}</span>
        </div>
      ))}
    </div>
  );
}

function RadialGauge({ percent, primary, secondary }) {
  const r = 40;
  const circumference = 2 * Math.PI * r;
  const offset = circumference * (1 - Math.min(1, Math.max(0, percent)));
  return (
    <div className="radial-gauge">
      <svg width="112" height="112" viewBox="0 0 100 100" className="radial-gauge-svg">
        <circle cx="50" cy="50" r={r} fill="transparent" stroke="var(--border-color)" strokeWidth="7" />
        <circle
          cx="50" cy="50" r={r} fill="transparent" stroke="var(--color-gold)" strokeWidth="7"
          strokeLinecap="round" strokeDasharray={circumference} strokeDashoffset={offset}
          transform="rotate(-90 50 50)"
        />
      </svg>
      <div className="radial-gauge-center">
        <span className="radial-gauge-primary">{primary}</span>
        <span className="radial-gauge-secondary">{secondary}</span>
      </div>
    </div>
  );
}

// Accordion form of the former "Attention Required" grid - same
// sections, same data, same click-through navigation; only the
// presentation changed (a collapsible list of pill rows instead of a
// multi-column grid), matching the Atelier design's accordion list.
function AttentionAccordion({ stock, orders, pendingTasks, upcomingDeliveries, pendingPurchases, delayedProduction, atRiskOrders }) {
  const navigate = useNavigate();
  const lowStock = (stock?.low_stock_action_list || []).slice(0, 4);
  const onHoldOrders = (orders?.top_orders || []).filter((o) => o.status === 'On Hold').slice(0, 4);
  const outstandingOrders = (orders?.top_orders || []).filter((o) => o.pending > 0).slice(0, 4);
  const tasks = (pendingTasks || []).slice(0, 4);
  const materialAtRisk = (atRiskOrders || []).slice(0, 4);

  // Memoized (not rebuilt fresh on every render) so the effect below
  // can depend on `sections` itself - a reference that only actually
  // changes when the underlying data does - instead of the previous
  // `sections.map((s) => s.key).join(',')` primitive-string workaround
  // used purely to get something stable enough to put in a dependency
  // array.
  const sections = React.useMemo(() => [
    {
      key: 'materialAtRisk', label: 'Orders At Risk - Material Shortage', items: materialAtRisk,
      renderItem: (o) => {
        const topMaterial = o.materials[0];
        const topSupplier = topMaterial?.supplier_options?.[0];
        return (
          <button key={o.order_id} className="attention-item" onClick={() => navigate(`/orders/${o.order_id}`)}>
            <span>
              {o.order_code} - {o.client_name || 'Client'}
              {topSupplier && (
                <span className="attention-item-hint">
                  {' '}Buy from {topSupplier.supplier_name}
                  {topSupplier.lead_time_days != null ? ` (${topSupplier.lead_time_days}d lead time)` : ''}
                </span>
              )}
            </span>
            <span className="status-badge status-danger">
              Short on {topMaterial?.material_name}{o.total_shortage_lines > 1 ? ` +${o.total_shortage_lines - 1} more` : ''}
            </span>
          </button>
        );
      },
    },
    {
      key: 'lowStock', label: 'Low Stock Materials', items: lowStock,
      renderItem: (m) => (
        <button key={m.material} className="attention-item" onClick={() => navigate(`/materials/${m.id}`)}>
          <span>{m.material}</span>
          <span className="status-badge status-warning">{m.current}/{m.minimum}</span>
        </button>
      ),
    },
    {
      key: 'onHold', label: 'Delayed Projects', items: onHoldOrders,
      renderItem: (o) => (
        <button key={o.order_id} className="attention-item" onClick={() => navigate(`/orders/${o.id}`)}>
          <span>{o.order_id} - {o.client}</span>
          <span className="status-badge status-neutral">On Hold</span>
        </button>
      ),
    },
    {
      key: 'outstanding', label: 'Outstanding Payments', items: outstandingOrders,
      renderItem: (o) => (
        <button key={o.order_id} className="attention-item" onClick={() => navigate(`/orders/${o.id}`)}>
          <span>{o.order_id} - {o.client}</span>
          <span className="status-badge status-warning">Rs {o.pending.toLocaleString()}</span>
        </button>
      ),
    },
    {
      key: 'tasks', label: 'Pending Tasks', items: tasks,
      renderItem: (t) => (
        <button key={t.id} className="attention-item" onClick={() => navigate(`/daily-tasks/${t.id}`)}>
          <span>{t.task_description}</span>
          <span className="status-badge status-warning">{t.priority || 'Normal'}</span>
        </button>
      ),
    },
    {
      key: 'deliveries', label: 'Upcoming Deliveries', items: upcomingDeliveries,
      renderItem: (o) => (
        <button key={o.id} className="attention-item" onClick={() => navigate(`/orders/${o.id}`)}>
          <span>{o.order_code} - {o.client?.name || 'Client'}</span>
          <span className="status-badge status-info">{new Date(o.delivery_date).toLocaleDateString()}</span>
        </button>
      ),
    },
    {
      key: 'purchases', label: 'Purchases Pending Payment', items: pendingPurchases,
      renderItem: (p) => (
        <button key={p.id} className="attention-item" onClick={() => navigate(`/purchases/${p.id}`)}>
          <span>{p.purchase_code} - {p.supplier?.name || 'Supplier'}</span>
          <span className="status-badge status-warning">{p.payment_status}</span>
        </button>
      ),
    },
    {
      key: 'production', label: 'Production Jobs Open 7+ Days', items: delayedProduction,
      renderItem: (j) => (
        <button key={j.id} className="attention-item" onClick={() => navigate(`/production-jobs/${j.id}`)}>
          <span>{j.job_code} - {j.operation || 'Job'}</span>
          <span className="status-badge status-warning">{j.status}</span>
        </button>
      ),
    },
  ].filter((s) => s.items.length > 0), [
    stock, orders, pendingTasks, upcomingDeliveries, pendingPurchases, delayedProduction, atRiskOrders, navigate,
  ]);

  const [openKey, setOpenKey] = useState(() => sections[0]?.key || null);
  // Always-current openKey without adding it to the effect's own
  // dependency array below - the same ref pattern this file already
  // uses for loadFollowUpsRef/loadCriticalDashboardDataRef further
  // down. openKey changes on every manual accordion click; depending
  // on it directly would re-run this effect on every such click for no
  // reason (it would never actually change setOpenKey's outcome, since
  // a manually-opened key is always a currently-valid one) - exactly
  // the unnecessary rerun this must avoid.
  const openKeyRef = useRef(openKey);
  openKeyRef.current = openKey;
  // Re-open the first genuinely populated section whenever the
  // populated set changes shape (e.g. everything just cleared, or the
  // previously-open section emptied out) - never leaves the accordion
  // stuck open on a section with nothing left in it. `sections` is now
  // a real, correctly-tracked dependency (memoized above against the
  // actual underlying data) rather than a stringified stand-in, so
  // this fires exactly when the section set's content genuinely
  // changes - no more, no less - and no longer needs an
  // eslint-disable to justify the dependency array.
  useEffect(() => {
    if (!sections.some((s) => s.key === openKeyRef.current)) {
      setOpenKey(sections[0]?.key || null);
    }
  }, [sections]);

  if (!sections.length) {
    return (
      <Card title="Attention Required" className="home-card">
        <div className="card-body" style={{ color: 'var(--text-secondary)' }}>Nothing needs attention right now.</div>
      </Card>
    );
  }

  return (
    <div className="accordion-attention">
      {sections.map((section) => {
        const isOpen = openKey === section.key;
        return (
          <div className="accordion-row" key={section.key}>
            <button
              type="button"
              className="accordion-row-header"
              onClick={() => setOpenKey(isOpen ? null : section.key)}
            >
              <span className="accordion-row-title">
                <span className="accordion-row-dot" />
                <span>{section.label} ({section.items.length})</span>
              </span>
              <span className={`accordion-chevron ${isOpen ? 'open' : ''}`}>&#9662;</span>
            </button>
            {isOpen && <div className="accordion-row-body">{section.items.map(section.renderItem)}</div>}
          </div>
        );
      })}
    </div>
  );
}

function DashboardPage() {
  const navigate = useNavigate();
  const { user } = useSelector((state) => state.auth);
  const isPrivileged = user?.role === 'master';
  const [stock, setStock] = useState(null);
  const [orders, setOrders] = useState(null);
  const [staff, setStaff] = useState(null);
  const [pendingTasks, setPendingTasks] = useState([]);
  const [activity, setActivity] = useState([]);
  const [upcomingDeliveries, setUpcomingDeliveries] = useState([]);
  const [pendingPurchases, setPendingPurchases] = useState([]);
  const [delayedProduction, setDelayedProduction] = useState([]);
  const [atRiskOrders, setAtRiskOrders] = useState([]);
  const [myTasks, setMyTasks] = useState([]);
  const [followUps, setFollowUps] = useState([]);

  const loadFollowUps = () => {
    clientActivitiesAPI.pendingFollowUps().then((res) => setFollowUps(res.data)).catch(() => {});
  };

  const handleCompleteFollowUp = (id) => {
    // Optimistic - the whole point of surfacing these is to let a
    // user clear their list quickly; wait for the round trip on
    // every click and it stops feeling worth using.
    setFollowUps((prev) => prev.filter((f) => f.id !== id));
    clientActivitiesAPI.completeFollowUp(id).catch(() => loadFollowUps());
  };

  // Same optimistic pattern as handleCompleteFollowUp above, applied
  // to the new Task Progress card's "mark done" control - a real
  // write (dailyTasksAPI.update, the same endpoint the Daily Tasks
  // page itself uses to change status), not a purely visual toggle
  // like the Stitch mockup's checklist.
  const handleMarkTaskDone = (id) => {
    setPendingTasks((prev) => prev.filter((t) => t.id !== id));
    dailyTasksAPI.update(id, { status: 'DONE' }).catch(() => {
      // Reload on failure so the task doesn't silently vanish from the
      // list if the write didn't actually go through.
      dailyTasksAPI.list({ status: 'TO DO', limit: 8 }).then((res) => setPendingTasks(res.data)).catch(() => {});
    });
  };

  const [widgetErrors, setWidgetErrors] = useState({});
  const [criticalSettled, setCriticalSettled] = useState({ stock: false, orders: false, staff: false });
  const classifyError = (err) => {
    if (err?.code === 'ECONNABORTED') return 'timeout';
    if (err?.response?.status >= 500) return 'server';
    if (!err?.response) return 'network';
    return 'unknown';
  };
  const errorMessageFor = (kind) => ({
    timeout: 'Taking longer than expected to load.',
    server: 'Something went wrong loading this. Please try again.',
    network: 'Could not reach the server.',
    unknown: 'Could not load this right now.',
  }[kind] || 'Could not load this right now.');

  const loadCriticalDashboardData = () => {
    setWidgetErrors({});
    const isFirstLoad = !stock && !orders && !staff;
    if (isFirstLoad) {
      // Only reset to "not yet settled" (which re-shows the loading
      // gate below) when there is genuinely no existing data to lose.
      // A refresh/retry while stock/orders/staff are already populated
      // must keep rendering that existing data while the new request
      // is in flight, not blank the page back to LoadingShell - see
      // section 7's "existing data must not disappear" requirement.
      setCriticalSettled({ stock: false, orders: false, staff: false });
    }
    // Each call is fully independent - one slow or failing widget
    // (most notably at-risk-orders, the genuinely more expensive
    // calculation) must never delay or block the others from
    // rendering the moment their own data is ready. criticalSettled
    // tracks completion (success OR failure) separately from the data
    // itself, specifically so a failed request can never leave the
    // whole page stuck on LoadingShell forever (see the render gate
    // below) - the previous `if (!stock || !orders || !staff)` gate
    // did exactly that: a single failed widget meant its state stayed
    // null permanently, silently, with the resulting widgetErrors
    // entry never actually reached by any render path.
    dashboardAPI.stock().then((res) => setStock(res.data))
      .catch((err) => setWidgetErrors((prev) => ({ ...prev, stock: classifyError(err) })))
      .finally(() => setCriticalSettled((prev) => ({ ...prev, stock: true })));
    dashboardAPI.orders().then((res) => setOrders(res.data))
      .catch((err) => setWidgetErrors((prev) => ({ ...prev, orders: classifyError(err) })))
      .finally(() => setCriticalSettled((prev) => ({ ...prev, orders: true })));
    dashboardAPI.staff().then((res) => setStaff(res.data))
      .catch((err) => setWidgetErrors((prev) => ({ ...prev, staff: classifyError(err) })))
      .finally(() => setCriticalSettled((prev) => ({ ...prev, staff: true })));
    dashboardAPI.atRiskOrders().then((res) => setAtRiskOrders(res.data.orders || []))
      .catch((err) => setWidgetErrors((prev) => ({ ...prev, atRisk: classifyError(err) })));
  };

  // loadFollowUps/loadCriticalDashboardData are plain functions redefined
  // every render (loadCriticalDashboardData genuinely needs to read the
  // latest stock/orders/staff on each call, for the isFirstLoad check
  // above) - listing either of them directly in the mount effect's own
  // dependency array below would make that effect re-fire every time
  // stock/orders/staff update, i.e. right after the very load it just
  // triggered, which is exactly the duplicate-call loop this must avoid.
  // Refs mirroring the latest closure sidestep that: reassigned on every
  // render (a plain assignment, not inside an effect, so it's never
  // stale), and reading/writing a ref's .current is exempt from
  // exhaustive-deps, so the effect below can call the always-current
  // function without needing either one as a dependency.
  const loadFollowUpsRef = useRef(loadFollowUps);
  loadFollowUpsRef.current = loadFollowUps;
  const loadCriticalDashboardDataRef = useRef(loadCriticalDashboardData);
  loadCriticalDashboardDataRef.current = loadCriticalDashboardData;

  useEffect(() => {
    // Critical, above-the-fold path first and unconditionally - the
    // KPI strip/operations snapshot render gate (allCriticalSettled
    // below) only ever waits on this.
    loadCriticalDashboardDataRef.current();

    // Everything below (Follow-ups, Task Progress, Upcoming Deliveries,
    // Production Execution, and the master-only Recent Activity feed)
    // renders further down the page, below the hero/operations-snapshot
    // content - see this file's own top-of-file layout comment. None of
    // it was ever part of the render gate (criticalSettled only tracks
    // stock/orders/staff), so this is a network-timing change only, not
    // a rendering one: deferred one idle tick past the critical calls
    // above (falling back to a macrotask where requestIdleCallback
    // isn't available) purely so 8 additional requests don't all
    // compete with stock/orders/staff/at-risk-orders for the browser's
    // limited concurrent-connection pool the instant the page mounts.
    // Same requests, same endpoints, same data, same
    // isPrivileged gating - just issued a beat later. Cancelled on
    // unmount/re-run so a fast navigation-away can't still fire these
    // for a page that's no longer there.
    let cancelled = false;
    const loadSecondaryDashboardData = () => {
      if (cancelled) return;
      loadFollowUpsRef.current();
      // limit bumped 4 -> 8: this same list now backs both the
      // Attention accordion (top 4, unchanged) and the new Task
      // Progress card (up to 6) below, instead of fetching it twice.
      dailyTasksAPI.list({ status: 'TO DO', limit: 8 }).then((res) => setPendingTasks(res.data)).catch(() => {});
      if (!isPrivileged) {
        // Excludes DONE tasks in SQL now - all 4 counts below only need
        // active work, not the employee's entire task history.
        dailyTasksAPI.list({ mine: true, exclude_status: 'DONE' }).then((res) => setMyTasks(res.data)).catch(() => {});
      }

      // Upcoming deliveries: orders with a delivery_date in the next 14
      // days that aren't already completed - filtered/sorted/limited in
      // SQL now (upcoming_delivery_within_days), not by downloading
      // every order ever placed and filtering in React.
      ordersAPI.list({ upcoming_delivery_within_days: 14, limit: 4 }).then((res) => {
        if (cancelled) return;
        setUpcomingDeliveries(res.data);
      }).catch(() => {});

      // Production jobs open 7+ days: there is no planned-completion-date
      // field on ProductionJob, so this is a stated approximation (same
      // pattern as the Orders "30+ days overdue" filter) - not a precise
      // "delayed" status the data doesn't actually support. Filtered/
      // limited in SQL now (open_longer_than_days), not by downloading
      // the entire table.
      productionJobsAPI.list({ open_longer_than_days: 7, limit: 4 }).then((res) => {
        if (cancelled) return;
        setDelayedProduction(res.data);
      }).catch(() => {});

      // Purchases/payments endpoints are
      // Depends(require_role("master")) server-side - a non-master
      // (employee) user firing these unconditionally was guaranteed 3
      // wasted round-trips per dashboard load, every one of them a 403.
      // Gated behind isPrivileged like the other master-only widgets.
      if (isPrivileged) {
        Promise.all([
          purchasesAPI.list({ limit: 4 }).then((r) => r.data).catch(() => []),
          paymentsAPI.list({ limit: 4 }).then((r) => r.data).catch(() => []),
          purchasesAPI.list({ pending_payment_only: true, limit: 4 }).then((r) => r.data).catch(() => []),
        ]).then(([recentPurchases, recentPayments, pendingPurchasesData]) => {
          if (cancelled) return;
          const feed = [
            ...recentPurchases.map((p) => ({ type: 'Purchase', description: `${p.purchase_code} - ${formatCurrency(p.invoice_total)}`, date: p.date })),
            ...recentPayments.map((p) => ({ type: 'Payment', description: `${p.receipt_code} - ${formatCurrency(p.amount)}`, date: p.date })),
          ].sort((a, b) => new Date(b.date) - new Date(a.date)).slice(0, 8);
          setActivity(feed);

          // Purchases still pending payment to the supplier - its own
          // bounded, filtered request now, not derived from the same
          // unbounded list used for the activity feed above.
          setPendingPurchases(pendingPurchasesData);
        });
      } else {
        setActivity([]);
        setPendingPurchases([]);
      }
    };

    const idle = window.requestIdleCallback || ((fn) => setTimeout(fn, 0));
    const cancelIdle = window.cancelIdleCallback || clearTimeout;
    const idleHandle = idle(loadSecondaryDashboardData);
    return () => { cancelled = true; cancelIdle(idleHandle); };
  }, [isPrivileged]);

  const allCriticalSettled = criticalSettled.stock && criticalSettled.orders && criticalSettled.staff;
  if (!allCriticalSettled) return <LoadingShell />;

  if (!stock || !orders || !staff) {
    // At least one critical widget genuinely failed (network/server/
    // timeout - see widgetErrors) rather than still being in flight.
    // This is the fix for the actual bug: previously this same
    // condition (!stock || !orders || !staff) meant "still loading"
    // unconditionally, so a single failed request left the whole page
    // on LoadingShell forever with no way out and no visible error -
    // exactly the "permanently spinning" failure this must not do.
    const failedWidgets = ['stock', 'orders', 'staff'].filter((k) => widgetErrors[k]);
    return (
      <div className="page">
        <Card title="Dashboard unavailable">
          <div className="card-body">
            <p style={{ color: 'var(--text-secondary)' }}>
              {failedWidgets.map((k) => errorMessageFor(widgetErrors[k])).join(' ') || 'Could not load the dashboard right now.'}
            </p>
            <button type="button" className="btn btn-primary" onClick={loadCriticalDashboardData}>
              Retry
            </button>
          </div>
        </Card>
      </div>
    );
  }

  // True aggregate from the backend now (overall_gross_margin_ratio,
  // computed across every order via SQL) - previously derived here
  // from order_profitability, which is deliberately bounded to only
  // the top 10 orders shown on this page, so this would have silently
  // understated margin for any business with more than 10 orders.
  const grossMargin = (orders.overall_gross_margin_ratio || 0) * 100;

  const hour = new Date().getHours();
  const greeting = hour < 5 ? 'Good night' : hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : hour < 21 ? 'Good evening' : 'Good night';
  const firstName = user?.full_name?.split(' ')[0] || '';

  // Same source data and same filter/slice logic as AttentionAccordion
  // below - kept side by side rather than computed twice from scratch,
  // so this summary and the detailed sections can never show different
  // counts for the same underlying situation.
  const topAttentionItems = [
    ...(atRiskOrders || []).slice(0, 4).map((o) => ({
      severity: 'critical', title: `${o.order_code} - ${o.client_name || 'Client'}`,
      detail: `Short on ${o.materials[0]?.material_name}${o.total_shortage_lines > 1 ? ` +${o.total_shortage_lines - 1} more` : ''}`,
      path: `/orders/${o.order_id}`,
    })),
    ...(stock?.low_stock_action_list || []).slice(0, 4).map((m) => ({
      severity: 'critical', title: m.material, detail: `${m.current}/${m.minimum} ${m.unit || ''} remaining`.trim(),
      path: `/materials/${m.id}`,
    })),
    ...(orders?.top_orders || []).filter((o) => o.pending > 0).slice(0, 4).map((o) => ({
      severity: 'warning', title: `${o.client} - ${o.order_id}`, detail: `Rs ${o.pending.toLocaleString()} outstanding`,
      path: `/orders/${o.id}`,
    })),
    ...(delayedProduction || []).slice(0, 4).map((j) => ({
      severity: 'warning', title: `${j.job_code} - ${j.operation || 'Production'}`, detail: `Open ${j.status?.toLowerCase() || ''}`.trim(),
      path: '/production-jobs',
    })),
  ].slice(0, 3);

  // --- KPI strip (compact pills, real data only) ---
  const kpiItems = [
    { icon: PurchaseIcon, label: 'Active Orders', value: orders.active_orders, tone: 'default' },
    { icon: AlertTriangleIcon, label: 'Materials at Risk', value: (atRiskOrders?.length || 0), tone: (atRiskOrders?.length || 0) > 0 ? 'warning' : 'default' },
    { icon: TruckIcon, label: 'Deliveries Due', value: upcomingDeliveries.length, tone: 'default' },
    ...(isPrivileged ? [{ icon: PaymentIcon, label: 'Payment Due', value: formatCurrency(orders.pending_payment), tone: orders.pending_payment > 0 ? 'warning' : 'default' }] : []),
    { icon: EmployeeIcon, label: 'Active Employees', value: staff.active_employees, tone: 'default' },
  ];

  // --- Orders Pipeline (real, dynamic project_status buckets - not a
  // hardcoded 5-stage taxonomy, since Order.project_status is a much
  // richer real workflow: Enquiry/Designing/.../Ready for Dispatch/
  // Installation/Completed/On Hold/Cancelled) ---
  const pipelineBars = (orders.order_pipeline || [])
    .filter((p) => p.orders > 0)
    .map((p) => ({ label: p.status, value: p.orders }));

  // --- Order health (real: OrderService.bulk_attention_flags counts,
  // the same risk levels the Orders list's own sort=risk uses) ---
  const risk = orders.delivery_risk_summary || { CRITICAL: 0, AT_RISK: 0, WATCH: 0, ON_TRACK: 0 };
  const riskTotal = risk.CRITICAL + risk.AT_RISK + risk.WATCH + risk.ON_TRACK;
  const onTrackPercent = riskTotal ? Math.round((risk.ON_TRACK / riskTotal) * 100) : 100;

  // --- Inventory health (real: stock_dashboard's own category_summary
  // items sum gives total active materials; low/critical are the same
  // low_stock_items/out_of_stock_items counts the KPI cards already use
  // elsewhere - no new calculation invented, just recombined) ---
  const totalMaterials = (stock.category_summary || []).reduce((sum, c) => sum + (c.items || 0), 0);
  const criticalMaterials = stock.out_of_stock_items || 0;
  const lowMaterials = stock.low_stock_items || 0;
  const healthyMaterials = Math.max(totalMaterials - criticalMaterials - lowMaterials, 0);
  const healthPercent = totalMaterials ? Math.round((healthyMaterials / totalMaterials) * 100) : 100;
  const inventoryBars = [
    { label: 'Healthy', value: healthyMaterials, color: 'var(--success)' },
    { label: 'Low', value: lowMaterials, color: 'var(--warning)' },
    { label: 'Critical', value: criticalMaterials, color: 'var(--danger)' },
  ];

  // --- Production execution (real: staff.production_status_summary,
  // the same GROUP BY the old linear pipeline widget used) ---
  const prodSummary = staff.production_status_summary || [];
  const prodTotal = prodSummary.reduce((sum, s) => sum + s.count, 0);
  const prodCompleted = prodSummary.find((s) => s.status === 'Completed')?.count || 0;
  const prodOpen = prodTotal - prodCompleted;
  const prodPercent = prodTotal ? prodCompleted / prodTotal : 0;

  return (
    <div className="page dashboard-page">
      <div className="dashboard-header">
        <span className="dashboard-eyebrow">Woodful Creations</span>
        <h1>{greeting}{firstName ? `, ${firstName}` : ''}.</h1>
        <p className="dashboard-subtitle">A live snapshot of inventory, sales, and operations across the business.</p>
      </div>

      <KpiStrip items={kpiItems} />

      {topAttentionItems.length > 0 && (
        <Card className="home-card">
          <div className="card-body">
            <h3 style={{ marginTop: 0 }}>{topAttentionItems.length} thing{topAttentionItems.length > 1 ? 's' : ''} need{topAttentionItems.length === 1 ? 's' : ''} your attention</h3>
            <div className="founder-attention-list">
              {topAttentionItems.map((item, idx) => (
                <div className="founder-attention-row" key={idx}>
                  <span className={`founder-attention-dot founder-attention-${item.severity}`} aria-hidden="true" />
                  <div className="founder-attention-text">
                    <strong>{item.title}</strong>
                    <span>{item.detail}</span>
                  </div>
                  <button className="btn-secondary" onClick={() => navigate(item.path)}>Review</button>
                </div>
              ))}
            </div>
          </div>
        </Card>
      )}

      <h2 className="section-heading">{isPrivileged ? 'Primary Business Metrics' : 'My Work'}</h2>
      <div className="hero-metrics">
        {isPrivileged ? (
          <>
            <div className="hero-metric">
              <span className="hero-label">Revenue</span>
              <span className="hero-value">{formatCurrency(orders.total_order_value)}</span>
            </div>
            <div className="hero-metric">
              <span className="hero-label">Outstanding</span>
              <span className="hero-value hero-warning">{formatCurrency(orders.pending_payment)}</span>
            </div>
            <div className="hero-metric">
              <span className="hero-label">Inventory Value</span>
              <span className="hero-value">{formatCurrency(stock.total_stock_value)}</span>
            </div>
            <div className="hero-metric">
              <span className="hero-label">Gross Margin</span>
              <span className="hero-value">{grossMargin.toFixed(1)}%</span>
            </div>
          </>
        ) : (
          <>
            <div className="hero-metric">
              <span className="hero-label">My Open Tasks</span>
              <span className="hero-value">{myTasks.filter((t) => t.status !== 'DONE').length}</span>
            </div>
            <div className="hero-metric">
              <span className="hero-label">Due Today</span>
              <span className="hero-value">{myTasks.filter((t) => t.status !== 'DONE' && t.date?.slice(0, 10) === today()).length}</span>
            </div>
            <div className="hero-metric">
              <span className="hero-label">Overdue</span>
              <span className="hero-value hero-warning">{myTasks.filter((t) => t.status !== 'DONE' && t.date?.slice(0, 10) < today()).length}</span>
            </div>
            <div className="hero-metric">
              <span className="hero-label">Blocked</span>
              <span className="hero-value">{myTasks.filter((t) => t.status === 'BLOCKED').length}</span>
            </div>
          </>
        )}
      </div>

      <div className="secondary-metrics">
        {isPrivileged && <KpiCard label="Amount Received" value={formatCurrency(orders.total_received)} />}
        <KpiCard label="Active Orders" value={orders.active_orders} />
        {orders.delivery_risk_summary && (
          <>
            <KpiCard
              label="Critical Orders" value={orders.delivery_risk_summary.CRITICAL || 0}
              tone={orders.delivery_risk_summary.CRITICAL > 0 ? 'danger' : 'success'}
              onClick={() => navigate('/orders', { state: { sortByRisk: true } })}
            />
            <KpiCard
              label="At Risk Orders" value={orders.delivery_risk_summary.AT_RISK || 0}
              tone={orders.delivery_risk_summary.AT_RISK > 0 ? 'warning' : 'success'}
              onClick={() => navigate('/orders', { state: { sortByRisk: true } })}
            />
          </>
        )}
        <KpiCard label="Active Employees" value={staff.active_employees} />
        <KpiCard label="Pending Tasks" value={staff.pending_tasks} tone={staff.pending_tasks > 0 ? 'warning' : 'success'} />
        <KpiCard label="Completed Tasks" value={staff.completed_tasks} tone="success" />
      </div>

      <section className="dashboard-section">
        <h2 className="section-heading">Operations Snapshot</h2>
        <div className="home-columns">
          {/* Column 1: Orders Pipeline, Order Health, Attention accordion */}
          <div className="home-column">
            <Card className="home-card home-card-flush home-card-tall">
              <div className="home-card-header">
                <div>
                  <span className="home-card-title">Orders Pipeline</span>
                  <span className="home-card-chip">{orders.active_orders} Active</span>
                </div>
                {isPrivileged && <span className="home-card-caption">{formatCurrency(orders.total_order_value)} total value</span>}
              </div>
              {pipelineBars.length ? <VerticalBars bars={pipelineBars} /> : (
                <div className="simple-chart-empty">No active orders yet.</div>
              )}
            </Card>

            <Card className="home-card home-card-flush">
              <div className="home-card-header">
                <span className="home-card-title">Order Health</span>
                <span className="home-card-caption">{onTrackPercent}% on track</span>
              </div>
              <div className="order-health-chips">
                <div className="order-health-chip order-health-danger">
                  <span className="order-health-count">{risk.CRITICAL}</span>
                  <span className="order-health-label">Critical</span>
                </div>
                <div className="order-health-chip order-health-warning">
                  <span className="order-health-count">{risk.AT_RISK}</span>
                  <span className="order-health-label">At Risk</span>
                </div>
                <div className="order-health-chip order-health-success">
                  <span className="order-health-count">{risk.WATCH + risk.ON_TRACK}</span>
                  <span className="order-health-label">On Track</span>
                </div>
              </div>
            </Card>

            <AttentionAccordion
              stock={stock} orders={orders} pendingTasks={pendingTasks}
              upcomingDeliveries={upcomingDeliveries} pendingPurchases={pendingPurchases} delayedProduction={delayedProduction}
              atRiskOrders={atRiskOrders}
            />
          </div>

          {/* Column 2: Inventory Health, Today's Focus */}
          <div className="home-column">
            <Card className="home-card home-card-flush home-card-tall">
              <div className="home-card-header">
                <div>
                  <span className="home-card-title">Inventory Health</span>
                  {isPrivileged && <span className="home-card-value">{formatCurrency(stock.total_stock_value)}</span>}
                </div>
                <span className="home-card-caption">Health: {healthPercent}%</span>
              </div>
              {totalMaterials ? <VerticalBars bars={inventoryBars} /> : (
                <div className="simple-chart-empty">No active materials yet.</div>
              )}
            </Card>

            <Card className="home-card home-card-flush" title={
              <span className="home-card-title-icon"><TruckIcon className="home-card-title-glyph" /> Today's Focus</span>
            }>
              {upcomingDeliveries.length === 0 ? (
                <div className="simple-chart-empty">No deliveries due in the next 14 days.</div>
              ) : (
                <div className="focus-list">
                  {upcomingDeliveries.map((o) => (
                    <button key={o.id} className="focus-row" onClick={() => navigate(`/orders/${o.id}`)}>
                      <span className="focus-row-icon"><TruckIcon /></span>
                      <span className="focus-row-text">
                        <strong>{o.order_code}</strong>
                        <span>{o.client?.name || 'Client'}</span>
                      </span>
                      <span className="status-badge status-info">{new Date(o.delivery_date).toLocaleDateString()}</span>
                    </button>
                  ))}
                </div>
              )}
            </Card>
          </div>

          {/* Column 3: Production Execution, Task Progress */}
          <div className="home-column">
            <Card className="home-card home-card-flush home-card-tall">
              <div className="home-card-header">
                <div>
                  <span className="home-card-title">Production Execution</span>
                  <span className="home-card-caption">
                    {prodSummary.map((s) => `${s.count} ${s.status}`).join(' • ') || 'No production jobs yet.'}
                  </span>
                </div>
                <button
                  className="home-card-link-btn" title="Go to Production Jobs"
                  onClick={() => navigate('/production-jobs')}
                >
                  <ArrowUpRightIcon />
                </button>
              </div>
              {prodTotal ? (
                <RadialGauge percent={prodPercent} primary={`${prodOpen} / ${prodTotal}`} secondary="Open Jobs" />
              ) : (
                <div className="simple-chart-empty">No production jobs yet.</div>
              )}
            </Card>

            <Card className="home-card home-card-flush" title={
              <span className="home-card-title-icon"><CompassIcon className="home-card-title-glyph" /> Task Progress</span>
            }>
              {pendingTasks.length === 0 ? (
                <div className="simple-chart-empty">No pending tasks right now.</div>
              ) : (
                <div className="task-progress-list">
                  {pendingTasks.slice(0, 6).map((t) => (
                    <div className="task-progress-row" key={t.id}>
                      <button className="task-progress-text" onClick={() => navigate(`/daily-tasks/${t.id}`)}>
                        <strong>{t.task_description}</strong>
                        <span>{t.priority || 'Normal'} priority{t.date ? ` • ${new Date(t.date).toLocaleDateString()}` : ''}</span>
                      </button>
                      <button
                        type="button" className="task-check-btn" title="Mark done"
                        onClick={() => handleMarkTaskDone(t.id)}
                        aria-label={`Mark "${t.task_description}" done`}
                      >
                        <CheckCircleIcon />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </div>
        </div>
      </section>

      {followUps.length > 0 && (
        <section className="dashboard-section">
          <h2 className="section-heading">Client Follow-ups Due</h2>
          <Card className="home-card">
            {followUps.map((f) => (
              <div className="follow-up-row" key={f.id}>
                <div>
                  <span
                    className="btn-link" onClick={() => navigate(`/clients/${f.client_id}`)}
                    style={{ fontWeight: 600, cursor: 'pointer' }}
                  >
                    {f.client_name || f.client_code}
                  </span>
                  {' — '}{f.summary}
                  <span className={f.overdue ? 'follow-up-overdue' : ''} style={{ marginLeft: 8 }}>
                    ({new Date(f.follow_up_date).toLocaleDateString()}{f.overdue ? ', overdue' : ''})
                  </span>
                </div>
                <span />
                <button className="btn-secondary" onClick={() => handleCompleteFollowUp(f.id)}>Mark Done</button>
              </div>
            ))}
          </Card>
        </section>
      )}

      <section className="dashboard-section">
        <h2 className="section-heading">Business at a Glance</h2>
        <div className="dashboard-grid">
          <Card className="home-card" title="Stock Value by Category">
            <SimpleBarChart data={stock.category_summary} labelKey="category" valueKey="stock_value" formatValue={formatCurrency} />
          </Card>
          <Card className="home-card" title="Top Orders & Payment Position">
            <Table
              columns={[
                { key: 'order_id', label: 'Order' }, { key: 'client', label: 'Client' },
                { key: 'pending', label: 'Pending', render: formatCurrency, align: 'right' }, { key: 'status', label: 'Status' },
              ]}
              data={orders.top_orders.slice(0, 5)}
            />
          </Card>
        </div>
      </section>

      <section className="dashboard-section">
        <h2 className="section-heading">Recent Activity</h2>
        <Card className="home-card">
          {activity.length === 0 ? (
            <div className="card-body" style={{ color: 'var(--text-secondary)' }}>No recent activity yet.</div>
          ) : (
            <div className="card-body">
              {activity.map((item, i) => (
                <div key={i} className="activity-row">
                  <span className="status-badge status-info">{item.type}</span>
                  <span className="activity-desc">{item.description}</span>
                  <span className="activity-date">{new Date(item.date).toLocaleDateString()}</span>
                </div>
              ))}
            </div>
          )}
        </Card>
      </section>
    </div>
  );
}

export default DashboardPage;
