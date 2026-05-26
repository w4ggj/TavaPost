        let supabaseClient;
        const supabaseUrl = "https://fntsthjupopvbwvmfsmz.supabase.co";
        const supabaseKey = "sb_publishable_MLMqkdV5LqZsqvq9JhN4kw_XrJvzjAS"; 
        const backendBaseUrl = "https://tavapost-backend.onrender.com";

        function initializeApp() {
            try {
                supabaseClient = supabase.createClient(supabaseUrl, supabaseKey);
                checkSession();
            } catch (err) {
                console.error("Core Engine Init Error: ", err.message);
                document.getElementById('system-crash-alert').className = "container view-active-block";
            }
        }

        function updateFileInputLabel() {
            const fileInput = document.getElementById('imageInput');
            const label = document.getElementById('file-label');
            if(fileInput.files.length > 0) {
                label.innerText = `✅ File Selected: ${fileInput.files[0].name}`;
                label.style.color = "var(--accent-green)";
            }
        }

        async function checkSession() {
            const { data: { session } } = await supabaseClient.auth.getSession();
            if (!session) {
                document.getElementById('view-login').className = "login-wrapper view-active-flex";
                document.getElementById('view-dashboard').className = "view-section";
                document.getElementById('header-logout').className = "view-section";
            } else {
                document.getElementById('view-login').className = "view-section";
                document.getElementById('view-dashboard').className = "container view-active-block";
                document.getElementById('header-logout').className = "btn btn-logout view-active-block";
                await handleZernioCallback();
                await loadSettings();
            }
        }

        async function signInUser() {
            const email = document.getElementById('login-email').value;
            const password = document.getElementById('login-password').value;
            const { error } = await supabaseClient.auth.signInWithPassword({ email, password });
            if (error) {
                const errorLabel = document.getElementById('login-error');
                errorLabel.innerText = `Login Failed: ${error.message}`;
                errorLabel.className = "text-red view-active-block";
            } else {
                await checkSession();
            }
        }

async function handleZernioCallback() {
    const urlParams = new URLSearchParams(window.location.search);
    const platform = localStorage.getItem('connecting_platform');

    // Only run if we were in the middle of a connect flow
    if (!platform || !urlParams.has('profileId')) return;

    const { data: { session } } = await supabaseClient.auth.getSession();
    if (!session) return;

    try {
        // Fetch real account IDs from Zernio
        const response = await fetch(`${backendBaseUrl}/api/get-accounts`);
        const data = await response.json();

        if (!data.accounts || data.accounts.length === 0) {
            return alert("Connected but could not find account. Check Zernio dashboard.");
        }

        // Find the account matching the platform we just connected
        const match = data.accounts.find(a => a.platform === platform);
        if (!match) {
            return alert(`No ${platform} account found in Zernio. Try connecting again.`);
        }

        // Store the real account _id
        let updateData = { user_id: session.user.id };
        if (platform === 'facebook') updateData.zernio_facebook_id = match._id;
        if (platform === 'instagram') updateData.zernio_instagram_id = match._id;

        const { error } = await supabaseClient.from('user_settings').upsert(updateData);
        if (!error) {
            window.history.replaceState({}, document.title, window.location.pathname);
            localStorage.removeItem('connecting_platform');
            await loadSettings();
        } else {
            console.error("Database write failed:", error);
        }
    } catch (err) {
        console.error("Callback error:", err);
    }
}

        async function loadSettings() {
            const { data: { session } } = await supabaseClient.auth.getSession();
            if (!session) return;

            const { data } = await supabaseClient
                .from('user_settings')
                .select('custom_prompt, zernio_facebook_id, zernio_instagram_id')
                .eq('user_id', session.user.id)
                .maybeSingle();

            if (data) {
                if (data.custom_prompt) document.getElementById('customPrompt').value = data.custom_prompt;
                
                const fbStatus = document.getElementById('fb-status');
                const fbAction = document.getElementById('fb-action-area');
                if (data.zernio_facebook_id) {
                    fbStatus.innerText = "Connected ✅";
                    fbStatus.className = "badge badge-green";
                    fbAction.innerHTML = `<button type="button" class="btn btn-disconnect" onclick="disconnectPlatform('facebook')">Disconnect Page</button>`;
                } else {
                    fbAction.innerHTML = `<button type="button" class="btn btn-fb" onclick="connectPlatform('facebook')">Connect Page</button>`;
                }
                
                const igStatus = document.getElementById('ig-status');
                const igAction = document.getElementById('ig-action-area');
                if (data.zernio_instagram_id) {
                    igStatus.innerText = "Connected ✅";
                    igStatus.className = "badge badge-green";
                    igAction.innerHTML = `<button type="button" class="btn btn-disconnect" onclick="disconnectPlatform('instagram')">Disconnect IG</button>`;
                } else {
                    igAction.innerHTML = `<button type="button" class="btn btn-ig" onclick="connectPlatform('instagram')">Connect IG</button>`;
                }
            }
        }

        async function saveSettings() {
            const { data: { session } } = await supabaseClient.auth.getSession();
            if (!session) return;
            await supabaseClient.from('user_settings').upsert({ user_id: session.user.id, custom_prompt: document.getElementById('customPrompt').value });
            const status = document.getElementById('save-status');
            status.className = "text-green view-active-block";
            setTimeout(() => status.className = "view-section", 3000);
        }

        async function connectPlatform(platform) {
    localStorage.setItem('connecting_platform', platform);
    
    // Call your backend to get the authUrl
    const response = await fetch(`${backendBaseUrl}/api/get-connect-url?platform=${platform}&profile_id=6a1350634beb548c15895d64&t=${Date.now()}`);
    const data = await response.json();
    
    if (data.authUrl) {
        // Redirect the user to Facebook's OAuth page
        window.location.href = data.authUrl;
    } else {
        alert("Failed to retrieve authorization URL.");
    }
}

async function disconnectPlatform(platform) {
    const { data: { session } } = await supabaseClient.auth.getSession();
    if (!session) return;

    const { data: settings } = await supabaseClient
        .from('user_settings')
        .select('zernio_facebook_id, zernio_instagram_id')
        .eq('user_id', session.user.id)
        .single();

    const accountId = platform === 'facebook' ? settings?.zernio_facebook_id : settings?.zernio_instagram_id;
    if (!accountId) return alert("No account ID found to disconnect.");

    if (!confirm(`Are you sure you want to disconnect your ${platform} account?`)) return;

    let update = { user_id: session.user.id };
    update[platform === 'facebook' ? 'zernio_facebook_id' : 'zernio_instagram_id'] = null;

    const { error } = await supabaseClient.from('user_settings').upsert(update);
    if (!error) {
        await loadSettings();
        alert("Account disconnected successfully.");
    } else {
        alert("Database error: " + error.message);
    }
}

async function generateDraft() {
    const fileInput = document.getElementById('imageInput');
    const loadingLabel = document.getElementById('loading');
    const btnGen = document.getElementById('btn-generate');

    if (!fileInput.files || fileInput.files.length === 0) {
        return alert("Please select an image file first.");
    }

    const { data: { session } } = await supabaseClient.auth.getSession();
    if (!session) return alert("Session expired. Please log in again.");

    loadingLabel.className = "view-active-block";
    btnGen.classList.add('btn-disabled');
    btnGen.disabled = true;
    document.getElementById('draft-cards').innerHTML = "";
    document.getElementById('selection-area').className = "view-section";

    const rawFile = fileInput.files[0];
    const customPromptValue = document.getElementById('customPrompt').value || "";

    try {
        let formData = new FormData();

        if (rawFile.size > 4 * 1024 * 1024) {
            // Compress large images before sending
            const img = new Image();
            img.src = URL.createObjectURL(rawFile);
            await new Promise(resolve => img.onload = resolve);

            const canvas = document.createElement('canvas');
            let w = img.width, h = img.height, max = 1920;
            if (w > h) { if (w > max) { h *= max / w; w = max; } }
            else { if (h > max) { w *= max / h; h = max; } }
            canvas.width = w; canvas.height = h;
            canvas.getContext('2d').drawImage(img, 0, 0, w, h);

            const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', 0.8));
            formData.append("file", blob, "compressed.jpg");
        } else {
            formData.append("file", rawFile);
        }

        formData.append("custom_prompt", customPromptValue);

        const response = await fetch(`${backendBaseUrl}/generate-draft?t=${Date.now()}`, {
            method: "POST",
            headers: { "Authorization": `Bearer ${session.access_token}` },
            body: formData
        });

        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.detail || `Server error ${response.status}`);
        }

        const data = await response.json();
        window.currentPostImageUrl = data.image_url;

        const container = document.getElementById('draft-cards');
        const options = data.draft_text.split(/(?:Option|Variation)?\s*\d+\.\s*/i).filter(t => t.trim().length > 0);

        if (options.length === 0) throw new Error("No caption variations were returned by the system.");

        options.forEach((txt, i) => {
            const card = document.createElement('div');
            card.className = "draft-card";
            card.innerHTML = `<header>DRAFT VARIATION ${i + 1}</header><p style="white-space:pre-wrap;">${txt.trim()}</p>`;
            card.onclick = () => { document.getElementById('finalCaption').value = txt.trim(); };
            container.appendChild(card);
        });

        document.getElementById('selection-area').className = "view-active-block";

    } catch (err) {
        console.error("Draft generation error:", err);
        alert("Generation failed: " + err.message);
    } finally {
        loadingLabel.className = "view-section";
        btnGen.classList.remove('btn-disabled');
        btnGen.disabled = false;
    }
}

async function publishToSocials() {
    const { data: { session } } = await supabaseClient.auth.getSession();
    if (!session) return alert("Session expired. Please log in again.");

    const caption = document.getElementById('finalCaption').value.trim();
    if (!caption) return alert("Please select or write a caption first.");

    const targetFB = document.getElementById('publish-to-fb').checked;
    const targetIG = document.getElementById('publish-to-ig').checked;

    if (!targetFB && !targetIG) return alert("Please select at least one platform.");

    const fileInput = document.getElementById('imageInput');
    if (!fileInput.files || fileInput.files.length === 0) return alert("Missing image file.");

    const btnPub = document.getElementById('btn-publish');
    btnPub.classList.add('btn-disabled');
    btnPub.disabled = true;
    btnPub.innerText = "Uploading Media & Publishing...";

    let finalImageUrl = "";

    try {
        // 1. Upload image to your tavapost-images Supabase Storage bucket
        const file = fileInput.files[0];
        const fileExt = file.name.split('.').pop();
        const fileName = `${Date.now()}.${fileExt}`;
        
        const { data: uploadData, error: uploadError } = await supabaseClient
            .storage
            .from('tavapost-images')
            .upload(fileName, file, {
                contentType: file.type || `image/${fileExt}`, // FORCE the image header
                cacheControl: '3600',
                upsert: false
            });

        if (uploadError) throw new Error("Image upload failed: " + uploadError.message);

        // 2. Get the public URL for Zernio
        const { data: publicUrlData } = supabaseClient
            .storage
            .from('tavapost-images') // Updated to your bucket name
            .getPublicUrl(fileName);
            
        finalImageUrl = publicUrlData.publicUrl;

        // 3. Fetch user settings for connected accounts
        const { data: settings, error } = await supabaseClient
            .from('user_settings')
            .select('zernio_facebook_id, zernio_instagram_id')
            .eq('user_id', session.user.id)
            .single();

        if (error || !settings) return alert("Error fetching account settings.");

        const platforms = [];
        if (targetFB) {
            if (!settings.zernio_facebook_id) return alert("Facebook is checked but no account is connected.");
            platforms.push({ platform: "facebook", accountId: settings.zernio_facebook_id });
        }
        if (targetIG) {
            if (!settings.zernio_instagram_id) return alert("Instagram is checked but no account is connected.");
            platforms.push({ platform: "instagram", accountId: settings.zernio_instagram_id });
        }

        // 4. Send the final URL and caption to your backend
        const response = await fetch(`${backendBaseUrl}/publish-post`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${session.access_token}`
            },
            body: JSON.stringify({
                image_url: finalImageUrl, // Sending the real URL to your backend
                caption: caption,
                platforms: platforms
            })
        });

        const result = await response.json();

        if (response.ok && result.status === "success") {
            alert("🚀 Successfully published to your selected platforms!");
        } else {
            alert("Publishing failed: " + (result.detail || JSON.stringify(result)));
        }
    } catch (err) {
        console.error("Publish error:", err);
        alert("Error: " + err.message);
    } finally {
        btnPub.classList.remove('btn-disabled');
        btnPub.disabled = false;
        btnPub.innerText = "🚀 Publish Directly to Social Channels";
    }
}
        async function signOutUser() { await supabaseClient.auth.signOut(); location.reload(); }
        window.onload = initializeApp;
