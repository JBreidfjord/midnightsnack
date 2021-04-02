const navAccount = document.getElementById('navbar-account');
const postsDropdown = document.getElementById('posts-dropdown');

if (document.cookie.split(';').some((item) => item.trim().startsWith('User='))) {
    const userName = document.cookie.split('; ').find(row => row.startsWith('User=')).split('=')[1];
    navAccount.innerHTML = `
    <li class="nav-item">
        <a class="nav-link" href="/logout">Logout</a>
    </li>
    <li class="nav-item">
        <a class="nav-link" href="/users/${userName}">${userName}</a>
    </li>
    `;
    if (document.cookie.split(';').some((item) => item.includes('post'))) {
        let fragment = document.createDocumentFragment();
        let a = document.createElement('a');
        let li = document.createElement('li');

        a.textContent = 'New';
        a.href = '/posts/create';
        a.className = 'dropdown-item';
        li.appendChild(a);
        fragment.appendChild(li);
        postsDropdown.appendChild(fragment);
        };
    if (document.cookie.split(';').some((item) => item.includes('edit'))) {
        let fragment = document.createDocumentFragment();
        let a = document.createElement('a');
        let li = document.createElement('li');

        a.textContent = 'Edit';
        a.href = '/posts/edit';
        a.className = 'dropdown-item';
        li.appendChild(a);
        fragment.appendChild(li);
        postsDropdown.appendChild(fragment);
        };
    if (document.cookie.split(';').some((item) => item.includes('admin'))) {
        let fragment = document.createDocumentFragment();
        let a = document.createElement('a');
        let li = document.createElement('li');

        a.textContent = 'Admin';
        a.href = '/admin';
        a.className = 'nav-link';
        li.className = 'nav-item';
        li.appendChild(a);
        fragment.appendChild(li);
        navAccount.appendChild(fragment);
        };
} else {
    navAccount.innerHTML = `
    <li class="nav-item">
        <a class="nav-link" href="/login">Login</a>
    </li>
    <li class="nav-item">
        <a class="nav-link" href="/register">Register</a>
    </li>
    `;
};