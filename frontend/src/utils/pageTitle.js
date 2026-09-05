// Centralized page-title mapping. One place to look up/update titles,
// rather than each page setting document.title itself.
const SUFFIX = 'Woodful Creations';

// Static routes: exact pathname match.
const STATIC_TITLES = {
  '/': 'Dashboard',
  '/dashboard': 'Dashboard',
  '/analytics': 'Analytics',
  '/inventory': 'Inventory',
  '/materials': 'Materials',
  '/materials/import': 'Material Import',
  '/locations': 'Locations',
  '/purchases': 'Purchases',
  '/purchases/import': 'Purchase Import',
  '/suppliers': 'Suppliers',
  '/products': 'Products',
  '/products/import': 'Product Import',
  '/company-holidays': 'Company Holidays',
  '/company-holidays/import': 'Holiday Import',
  '/estimates': 'Estimates',
  '/estimates/import': 'Estimate Import',
  '/orders': 'Orders',
  '/orders/import': 'Order Import',
  '/rate-master': 'Rate Master',
  '/rate-master/import': 'Rate Card Import',
  '/issues': 'Issues',
  '/clients': 'Clients',
  '/clients/import': 'Client Import',
  '/payments': 'Payments',
  '/project-expenses': 'Project Expenses',
  '/employees': 'Employees',
  '/attendance': 'Attendance',
  '/leaves': 'Leaves',
  '/daily-tasks': 'Daily Tasks',
  '/production-jobs': 'Production Jobs',
  '/settings': 'Settings',
  '/learning-candidates': 'Learning Candidates',
  '/users': 'Users',
  '/audit-logs': 'Audit Logs',
  '/candidates': 'Candidates',
  '/interviews': 'Interviews',
  '/salary-slips': 'Salary Slips',
  '/mobile-app': 'Mobile App',
  '/login': 'Log In',
  '/forgot-password': 'Forgot Password',
  '/reset-password': 'Reset Password',
};

// Dynamic routes: prefix + a short label for the id segment.
const DYNAMIC_TITLES = [
  { prefix: '/materials/', label: 'Material' },
  { prefix: '/products/', label: 'Product' },
  { prefix: '/suppliers/', label: 'Supplier' },
  { prefix: '/purchases/', label: 'Purchase' },
  { prefix: '/clients/', label: 'Client' },
  { prefix: '/orders/', label: 'Order' },
  { prefix: '/employees/', label: 'Employee' },
  { prefix: '/daily-tasks/', label: 'Task' },
  { prefix: '/production-jobs/', label: 'Production Job' },
  { prefix: '/estimates/', label: 'Estimate' },
  { prefix: '/candidates/', label: 'Candidate' },
];

export function titleForPath(pathname) {
  if (STATIC_TITLES[pathname]) return `${STATIC_TITLES[pathname]} | ${SUFFIX}`;
  for (const { prefix, label } of DYNAMIC_TITLES) {
    if (pathname.startsWith(prefix) && pathname.length > prefix.length) {
      const id = pathname.slice(prefix.length).split('/')[0];
      if (id) return `${label} ${id} | ${SUFFIX}`;
    }
  }
  return SUFFIX;
}

export function setDocumentTitle(pathname) {
  document.title = titleForPath(pathname);
}
