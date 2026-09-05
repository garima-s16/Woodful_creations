import React from 'react';
import './OrderLifecycle.css';

// The real, existing 11-stage production pipeline (ORDER_PROJECT_STATUSES
// in app/utils/status_rules.py) - not an invented sequence. "On Hold" and
// "Cancelled" are reachable from any stage rather than being stages
// themselves, so they're shown as a status overlay rather than a step.
const STAGES = [
  'Enquiry', 'Designing', 'Approved', 'Material Purchase', 'Cutting',
  'Edge Banding', 'Assembly', 'Painting', 'Ready for Dispatch', 'Installation', 'Completed',
];

const SUB_TRACKS = [
  { key: 'design_status', label: 'Design' },
  { key: 'execution_status', label: 'Execution' },
  { key: 'delivery_status', label: 'Delivery' },
];

function SubTrackDot({ state }) {
  const cls = state === 'Completed' ? 'sub-dot-done' : state === 'In Progress' ? 'sub-dot-active' : 'sub-dot-pending';
  return <span className={`order-lifecycle-sub-dot ${cls}`} aria-hidden="true" />;
}

/* Visualizes Order.project_status as a spatial progression through
   Woodful's real production stages, with design/execution/delivery shown
   as three parallel tracks alongside it - these move independently of
   the main stage (e.g. Delivery can still be Pending while Painting is
   already underway), so folding them into one sequence would misrepresent
   the real state rather than clarify it. */
function OrderLifecycle({ order }) {
  const isHalted = order.project_status === 'On Hold' || order.project_status === 'Cancelled';
  const currentIndex = STAGES.indexOf(order.project_status);

  return (
    <div className="order-lifecycle">
      <div className={`order-lifecycle-track ${isHalted ? 'order-lifecycle-track-halted' : ''}`} role="list" aria-label="Order production stage">
        {STAGES.map((stage, i) => {
          // While halted, project_status itself no longer points at any
          // real stage in STAGES (it's "On Hold"/"Cancelled", a side-state)
          // and the backend doesn't record what stage the job was at
          // beforehand - so every step is shown as neutral/pending rather
          // than guessing or fabricating how far it got.
          const isPast = !isHalted && i < currentIndex;
          const isCurrent = !isHalted && i === currentIndex;
          return (
            <div
              key={stage}
              role="listitem"
              className={`order-lifecycle-step ${isPast ? 'order-lifecycle-step-done' : ''} ${isCurrent ? 'order-lifecycle-step-current' : ''}`}
              title={stage}
            >
              <span className="order-lifecycle-dot" aria-hidden="true" />
              <span className="order-lifecycle-step-label">{stage}</span>
            </div>
          );
        })}
      </div>
      {isHalted && (
        <span className={`status-badge ${order.project_status === 'Cancelled' ? 'status-danger' : 'status-warning'} order-lifecycle-halt-badge`}>
          {order.project_status}
        </span>
      )}
      <div className="order-lifecycle-subtracks">
        {SUB_TRACKS.map(({ key, label }) => (
          <div className="order-lifecycle-subtrack" key={key}>
            <SubTrackDot state={order[key]} />
            <span className="order-lifecycle-subtrack-label">{label}</span>
            <span className="order-lifecycle-subtrack-state">{order[key]}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default OrderLifecycle;
