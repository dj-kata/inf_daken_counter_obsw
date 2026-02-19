"""
English UI Definition
All UI strings defined as class member variables
IDE autocomplete friendly format
"""


class UIText:
    """UI text definition class"""
    
    class menu:
        """Menu bar"""
        file = '&File'
        tool = '&Tool'
        language = '&Language'
        help = '&Help'
        
        # File menu
        base_config = 'Configure(&C)...'
        obs_config = 'OBS Settings(&O)...'
        save_image = '&Save Image'
        exit = 'E&xit'
        
        # ツールメニュー
        tweet = '&Tweet today playlog'
        score_viewer = '&Score Viewer'
        write_bpi_csv = 'Generate csv for BPI Manager(coming soon)(&B)...'
        
        # Language menu
        japanese = '日本語'
        english = 'English'
        
        # Help menu
        about = '&About'
        documentation = '&Documentation'
    
    class window:
        """Window titles"""
        main_title = 'INFINITAS daken counter'
        settings_title = 'Settings'
        obs_title = 'OBS Control Settings'
        about_title = 'About'
        major_update_title = 'TODO: Major update dialog title'
        import_v2_config_title = 'TODO: v2 config import dialog title'
    
    class dialog:
        """Dialogs"""
        ok = 'OK'
        cancel = 'Cancel'
        apply = 'Apply'
        close = 'Close'
        yes = 'Yes'
        no = 'No'
        browse = 'Browse...'
        select_image_path = 'Select path for saving images'
    
    class tab:
        """Settings dialog tabs"""
        feature = 'Features'
        music_pack = 'Music Packs'
        image_save = 'Image Saving'
        data_import = 'Data Import'
        rival = 'Rival'
    
    class feature:
        """Feature settings tab"""
        tweet_group = 'Tweet Function'
        enable_autotweet = 'Enable auto-tweet on exit'
        enable_judge = 'Include judge data'
        enable_folder_updates = 'Show folder update count(coming soon)'
        
        other_group = 'Other'
        image_save_path = 'Image save path:'
        autoload_offset = 'Auto-load offset:'
        websocket_port = 'Data display port:'
        keep_on_top = 'Always on Top'
    
    class music_pack:
        """Music pack settings tab"""
        description = 'Select music packs to include in statistics'
        select_all = 'Select All'
        deselect_all = 'Deselect All'
    
    class image_save:
        """Image save settings tab"""
        condition_group = 'Image Save Condition'
        always = 'Always save'
        only_updates = 'Save on update only'
        never = 'Never save'
        
        rivalarea_group = 'Rival Area Editing'
        rivalarea_invalid = 'Do not edit'
        rivalarea_mosaic = 'Blur'
        rivalarea_cut = 'Cut'
        # rivalarea_hide = 'Hide'
        # rivalarea_custom = 'Replace with custom image'
        
        other_group = 'Others'
        write_statistics = 'Write statistics'
    
    class data_import:
        """Data import tab"""
        from_images_group = 'Import from Result Images'
        from_images_button = 'Select folder to import'
        from_images_dialog_description = 'Select a result image folder'
        from_images_description = 'Select a folder containing result images (PNG)'
        
        from_pkl_group = 'Import from alllog.pkl of v2'
        from_pkl_button = 'Select alllog.pkl to import'
        from_pkl_description = 'Select alllog.pkl file saved by inf_daken_counter v2'
        from_pkl_dialog_description = 'Select alllog.pkl'
        
        cancel_button = 'Cancel'
        processing = 'Processing...'
        completed_format = 'Completed: Registered {registered} out of {total} items'
        error_format = 'Error: {message}'
    
    class rival:
        """Rival settings tab"""
        rival_group = 'Rival Registration'
        rival_description = 'Register Google Drive share URLs for rival inf_score.csv files'
        name_label = 'Name'
        url_label = 'URL'
        add_button = 'Add'
        remove_button = 'Remove'
        csv_export_group = 'CSV Export Path'
        csv_export_description = 'Output folder for inf_score.csv (empty = app root)'
        select_csv_export_path = 'Select CSV export folder'

    class message:
        """Messages"""
        language_changed = 'Language changed. Restarting application...'
        config_saved = 'Settings saved'
        restart_required = 'Please restart the application to apply settings'
        confirm_restart = 'Language setting will be changed. Restart application?'
        select_action = 'Select an action'
        select_timing = 'Select trigger timing'
        select_scene_and_source = 'Select target scene and source'
        select_next_scene = 'Select destination scene'
        failed_add_setting = 'Failed to add setting:\n{e}'
        select_setting_to_remove = 'Select a setting to remove'
        ask_remove_all_settings = 'Delete all control settings?\n(Monitored sources will not be deleted)'
        removed_all_settings = 'All control settings deleted.\n(Monitored sources were kept)'
        reconnected_to_obs = 'Reconnected to OBS'
        failed_reconnection_to_obs = 'Failed to reconnect to OBS'
        failed_reconnection_to_obs_with_error = 'Failed to reconnect to OBS:\n{e}'
        target_source_removed = 'Monitored source cleared'
        
        major_update = 'TODO: Major update notification message'
        ask_import_v2_config = 'TODO: v2 config import confirmation message'

        error_title = 'Error'
        warning_title = 'Warning'
        info_title = 'Information'
        confirm_title = 'Confirm'
        completed_title = 'Completed'
        success = 'Success'
    
    class status:
        """Status bar"""
        ready = 'Ready'
        processing = 'Processing...'
        saved = 'Saved'
        loading = 'Loading...'
        canceling = 'Cancelling...'
    
    class button:
        """Buttons"""
        ok = 'OK'
        cancel = 'Cancel'
        clear = 'Clear'
        start = 'Start'
        stop = 'Stop'
        pause = 'Pause'
        resume = 'Resume'
        reset = 'Reset'
        save = 'Save'
        load = 'Load'
        refresh = 'Refresh'
        reconnect = 'Reconnect'
        add_setting = 'Add setting'
        delete_selected_setting = 'Remove selected setting'
        delete_all_settings = 'Remove all'

    class obs:
        '''OBS関連のメッセージ'''
        connection_state = 'OBS Status'
        status_connected = 'Connected'
        status_connection_failed = 'Connection failed'
        status_disconnected = 'Disconnected'
        status_lost = 'Connection was lost'
        status_reconnect_failed = 'Reconnection failed'
        status_reconnecting = 'Reconnecting...'
        status_reconnected = 'Reconnected'
        not_configured = "Not configured"
        not_connected  = "Not connected"
        no_source = "Target source is not set"
        connected = 'Connected'

        # 制御設定ダイアログ関連
        websocket_group = 'OBS WebSocket Connect Settings'
        websocket_host = 'host:'
        websocket_port = 'port:'
        websocket_password = 'password:'
        target_source_group = 'Monitored Sources'
        target_source_not_set = 'Not Set'
        target_source_label = 'Current Target:'
        new_settings_group = 'Add New Control Setting'
        new_settings_action = 'Action:'
        new_settings_timing = 'Trigger Timing:'
        new_settings_target_scene = 'Target Scene:'
        new_settings_source = 'Target Source:'
        new_settings_next_scene = 'Switch to Scene:'
        registered_group = 'Registered Control Settings'
        timing = 'Timing'
        action = 'Action'
        scene = 'Scene'
        source = 'Source'
        setting_complete = 'Settings Saved'
        source_configured = "Monitored source set to '{target_source}'"

    class obs_timing:
        '''timing for obs control settings'''
        app_start = "app start"
        app_end = "app exit"
        select_start = "song selection start"
        select_end = "song selection end"
        play_start = "gameplay start"
        play_end = "gameplay end"
        result_start = "result screen start"
        result_end = "result screen end"

    class obs_action:
        '''action for obs control settings'''
        show_source = "show source"
        hide_source = "hide source"
        switch_scene = "switch scene"
        set_monitor_source = "set monitor source"
        autosave_source = "auto-save capture of source"

    class main:
        '''main window'''
        other_info = 'Other information'
        current_mode = 'mode:'
        ontime = 'ontime:'
        today_notes = 'today notes:'
        num_saved_results = 'saved results:'
        last_saved_song = 'last saved song:'
        save_image = 'Save Image (F6)'
        status_ready = 'Ready'

    class mode:
        '''検出モード用'''
        init = '-'
        play = 'play'
        result = 'result'
        select = 'music select'
        option = 'option'
