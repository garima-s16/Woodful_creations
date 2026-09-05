import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useDispatch, useSelector } from 'react-redux';
import { updateQuantity, removeFromCart, clearCart } from '../../../redux/slices/cartSlice';
import { formatCurrency } from '../../../utils/format';
import { CloseIcon, CartIcon } from '../../../components/icons';
import '../../../styles/CartDrawer.css';

function CartDrawer({ open, onClose }) {
  const items = useSelector((state) => state.cart.items);
  const dispatch = useDispatch();
  const navigate = useNavigate();

  const shortfallOf = (item) => {
    if (item.currentStock === null || item.currentStock === undefined) return null;
    return Math.max(0, item.quantity - item.currentStock);
  };

  const itemsNeedingPurchase = items.filter((i) => {
    const s = shortfallOf(i);
    return s === null || s > 0;
  });
  const purchaseValue = items.reduce((sum, i) => {
    const s = shortfallOf(i);
    const purchaseQty = s === null ? i.quantity : s;
    return sum + (Number(i.rate) || 0) * purchaseQty;
  }, 0);

  const startPurchase = (item) => {
    const shortfall = shortfallOf(item);
    // Only the shortfall needs buying - if stock already covers what's
    // needed, don't send the full required quantity into a purchase.
    const purchaseQty = shortfall === null ? item.quantity : shortfall;
    navigate('/purchases', {
      state: {
        openCreate: true,
        prefill: {
          material_id: item.materialId,
          supplier_id: item.supplierId || '',
          quantity: purchaseQty,
          rate: item.rate || '',
          unit: item.unit || '',
        },
      },
    });
    onClose();
  };

  return (
    <>
      <div className={`cart-drawer-backdrop ${open ? 'open' : ''}`} onClick={onClose} />
      <aside className={`cart-drawer ${open ? 'open' : ''}`} aria-hidden={!open}>
        <div className="cart-drawer-header">
          <h3><CartIcon width={18} height={18} /> Purchase Cart</h3>
          <button className="cart-drawer-close" onClick={onClose} aria-label="Close cart"><CloseIcon width={18} height={18} /></button>
        </div>

        {items.length === 0 ? (
          <div className="cart-drawer-empty">
            <p className="cart-drawer-empty-title">Your purchase cart is empty.</p>
            <p className="cart-drawer-empty-sub">Browse the Material Catalog and add what you need to purchase.</p>
            <button className="btn-secondary" onClick={() => { navigate('/materials'); onClose(); }}>Browse Materials</button>
          </div>
        ) : (
          <>
            <div className="cart-drawer-items">
              {items.map((item) => {
                const shortfall = shortfallOf(item);
                return (
                <div className="cart-drawer-item" key={item.materialId}>
                  <div className="cart-drawer-item-main">
                    <div className="cart-drawer-item-name">{item.name}</div>
                    {item.supplierName && <div className="cart-drawer-item-supplier">Preferred: {item.supplierName}</div>}
                    {shortfall !== null && (
                      <div className="cart-drawer-item-shortage">
                        Required: {item.quantity} &middot; Stock: {item.currentStock} &middot;{' '}
                        {shortfall > 0
                          ? <strong className="cart-drawer-shortage-buy">Purchase: {shortfall}</strong>
                          : <span className="cart-drawer-shortage-covered">Fully covered by stock</span>}
                      </div>
                    )}
                  </div>
                  <div className="cart-drawer-item-qty">
                    <button aria-label={`Decrease quantity of ${item.name}`} onClick={() => dispatch(updateQuantity({ materialId: item.materialId, quantity: item.quantity - 1 }))}>{'\u2212'}</button>
                    <span aria-live="polite">{item.quantity}</span>
                    <button aria-label={`Increase quantity of ${item.name}`} onClick={() => dispatch(updateQuantity({ materialId: item.materialId, quantity: item.quantity + 1 }))}>+</button>
                  </div>
                  <div className="cart-drawer-item-value">{item.rate ? formatCurrency(item.rate * item.quantity) : '\u2014'}</div>
                  <div className="cart-drawer-item-actions">
                    <button className="btn-link" onClick={() => startPurchase(item)} disabled={shortfall === 0}>
                      {shortfall === 0 ? 'No Purchase Needed' : 'Start Purchase'}
                    </button>
                    <button className="cart-drawer-remove" onClick={() => dispatch(removeFromCart(item.materialId))} aria-label="Remove item">
                      <CloseIcon width={14} height={14} />
                    </button>
                  </div>
                </div>
                );
              })}
            </div>
            <div className="cart-drawer-footer">
              <div className="cart-drawer-total">
                <span>Items to purchase</span>
                <strong>{itemsNeedingPurchase.length}</strong>
              </div>
              <div className="cart-drawer-total">
                <span>Estimated purchase value</span>
                <strong>{formatCurrency(purchaseValue)}</strong>
              </div>
              <button className="btn-secondary" onClick={() => dispatch(clearCart())}>Clear Cart</button>
            </div>
          </>
        )}
      </aside>
    </>
  );
}

export default CartDrawer;
